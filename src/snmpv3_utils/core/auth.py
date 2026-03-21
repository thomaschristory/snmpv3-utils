# src/snmpv3_utils/core/auth.py
"""Credential verification operations.

check_creds: test a single USM credential set against a host.
bulk_check: test all rows from a CSV credential file against a single host.
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pysnmp.hlapi.v3arch.asyncio import UdpTransportTarget, UsmUserData

from snmpv3_utils.core.query import _get, get
from snmpv3_utils.security import (
    AuthProtocol,
    Credentials,
    PrivProtocol,
    SecurityLevel,
    build_usm_user,
)
from snmpv3_utils.types import AuthResult, VarBindError

if TYPE_CHECKING:
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

_SYSDESCR_OID = "1.3.6.1.2.1.1.1.0"
_DEFAULT_MAX_CONCURRENT = 10


def _parse_row_to_usm(row: dict[str, str]) -> UsmUserData:
    """Parse a CSV row dict into a UsmUserData object.

    Raises ValueError on invalid enum values or missing required fields.
    """
    raw_auth = row.get("auth_protocol")
    raw_priv = row.get("priv_protocol")
    auth_proto = AuthProtocol(raw_auth) if raw_auth else None
    priv_proto = PrivProtocol(raw_priv) if raw_priv else None
    sec_level = SecurityLevel(row.get("security_level", "noAuthNoPriv"))
    creds = Credentials(
        username=row.get("username", ""),
        auth_protocol=auth_proto,
        auth_key=row.get("auth_key") or None,
        priv_protocol=priv_proto,
        priv_key=row.get("priv_key") or None,
        security_level=sec_level,
    )
    return build_usm_user(creds)


def check_creds(
    host: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
    username: str = "",
) -> AuthResult:
    """Test credentials by performing a GET on sysDescr.

    Returns {"status": "ok", ...} or {"status": "failed", "error": ..., ...}.
    """
    result = get(host, _SYSDESCR_OID, usm, port=port, timeout=timeout, retries=retries)
    if "error" in result:
        err = cast(VarBindError, result)
        return {"status": "failed", "host": host, "username": username, "error": err["error"]}
    return {"status": "ok", "host": host, "username": username, "sysdescr": result["value"]}


async def _check_creds_async(
    engine: SnmpEngine,
    host: str,
    usm: UsmUserData,
    username: str,
    transport: UdpTransportTarget,
) -> AuthResult:
    """Async credential check: GET sysDescr using pre-built engine + transport."""
    result = await _get(engine, host, _SYSDESCR_OID, usm, transport)
    if "error" in result:
        err = cast(VarBindError, result)
        return {"status": "failed", "host": host, "username": username, "error": err["error"]}
    return {"status": "ok", "host": host, "username": username, "sysdescr": result["value"]}


async def _bulk_check_async(
    host: str,
    csv_path: Path,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
) -> list[AuthResult]:
    """Async bulk credential check with optional concurrency limit."""
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        # Transport creation failed — return all-failed for every CSV row
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        return [
            {
                "status": "failed",
                "host": host,
                "username": row.get("username", ""),
                "error": str(exc),
            }
            for row in rows
        ]

    sem = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    results: list[AuthResult | None] = [None] * len(rows)
    tasks: list[tuple[int, asyncio.Task[AuthResult]]] = []

    for i, row in enumerate(rows):
        try:
            usm = _parse_row_to_usm(row)
        except ValueError as e:
            results[i] = {
                "status": "failed",
                "host": host,
                "username": row.get("username", ""),
                "error": str(e),
            }
            continue

        async def _check_one(
            usm: UsmUserData = usm, username: str = row.get("username", "")
        ) -> AuthResult:
            if sem:
                async with sem:
                    return await _check_creds_async(engine, host, usm, username, transport)
            return await _check_creds_async(engine, host, usm, username, transport)

        tasks.append((i, asyncio.create_task(_check_one())))

    if tasks:
        gathered = await asyncio.gather(*(t for _, t in tasks))
        for (i, _), result in zip(tasks, gathered, strict=True):
            results[i] = result

    return results  # type: ignore[return-value]


def bulk_check(
    host: str,
    csv_path: Path,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
) -> list[AuthResult]:
    """Test every credential row in a CSV against a single host.

    CSV format: username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
    Returns a list of check_creds results, one per row.

    max_concurrent: max parallel SNMP checks (default 10). None = no limit.
    """
    return asyncio.run(_bulk_check_async(host, csv_path, max_concurrent=max_concurrent))
