# src/snmpv3_utils/core/query.py
"""SNMP query operations: GET, GETNEXT, WALK, BULK, SET.

All functions return plain dicts or list of dicts — no rich, no CLI.
Errors are returned as {"error": "<message>"} — never raised.
"""

import asyncio
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    ContextData,
    Integer,
    ObjectIdentity,
    ObjectType,
    OctetString,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
)
from pysnmp.hlapi.v3arch.asyncio import (
    bulk_cmd as _bulk_cmd_async,
)
from pysnmp.hlapi.v3arch.asyncio import (
    get_cmd as _get_cmd_async,
)
from pysnmp.hlapi.v3arch.asyncio import (
    next_cmd as _next_cmd_async,
)
from pysnmp.hlapi.v3arch.asyncio import (
    set_cmd as _set_cmd_async,
)
from pysnmp.hlapi.v3arch.asyncio import (
    walk_cmd as _walk_cmd_async,
)

from snmpv3_utils.types import SetResult, VarBindResult, VarBindSuccess

# ---------------------------------------------------------------------------
# Var-bind helper
# ---------------------------------------------------------------------------


def _var_bind_to_dict(var_bind: Any) -> VarBindSuccess:
    return {"oid": var_bind[0].prettyPrint(), "value": var_bind[1].prettyPrint()}


# ---------------------------------------------------------------------------
# Async internals — reusable from other async contexts (e.g. bulk_check).
# The _*_cmd_async aliases above are the mock targets in tests.
# ---------------------------------------------------------------------------


async def _get(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> VarBindResult:
    """Async GET: fetch a single OID value."""
    try:
        error_indication, error_status, _, var_binds = await _get_cmd_async(
            engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return _var_bind_to_dict(var_binds[0])


async def _get_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> VarBindResult:
    """Self-contained async GET: creates engine + transport in one event loop."""
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _get(engine, host, oid, usm, transport)


async def _getnext(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> VarBindResult:
    """Async GETNEXT: return the next OID after the given one."""
    try:
        error_indication, error_status, _, var_binds = await _next_cmd_async(
            engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return _var_bind_to_dict(var_binds[0])


async def _getnext_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> VarBindResult:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _getnext(engine, host, oid, usm, transport)


async def _walk(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> list[VarBindResult]:
    """Async WALK: traverse subtree via repeated GETNEXT."""
    results: list[VarBindResult] = []
    async for error_indication, error_status, _, var_binds in _walk_cmd_async(
        engine,
        usm,
        transport,
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append(
                {"error": str(error_indication or error_status), "host": host, "oid": oid}
            )
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


async def _walk_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> list[VarBindResult]:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    return await _walk(engine, host, oid, usm, transport)


async def _bulk(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    """Async GETBULK retrieval."""
    try:
        error_indication, error_status, _, var_binds = await _bulk_cmd_async(
            engine,
            usm,
            transport,
            ContextData(),
            0,
            max_repetitions,
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        )
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    results: list[VarBindResult] = []
    if error_indication or error_status:
        results.append({"error": str(error_indication or error_status), "host": host, "oid": oid})
    else:
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


async def _bulk_with_transport(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int,
    timeout: int,
    retries: int,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    return await _bulk(engine, host, oid, usm, transport, max_repetitions)


async def _set_oid(
    engine: SnmpEngine,
    host: str,
    oid: str,
    snmp_value: Any,
    value: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> SetResult:
    """Async SET: set an OID to a value."""
    try:
        error_indication, error_status, _, _ = await _set_cmd_async(
            engine,
            usm,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid), snmp_value),
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return {"status": "ok", "host": host, "oid": oid, "value": value}


async def _set_oid_with_transport(
    host: str,
    oid: str,
    snmp_value: Any,
    value: str,
    usm: UsmUserData,
    port: int,
    timeout: int,
    retries: int,
) -> SetResult:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _set_oid(engine, host, oid, snmp_value, value, usm, transport)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> VarBindResult:
    """Fetch a single OID value."""
    return asyncio.run(_get_with_transport(host, oid, usm, port, timeout, retries))


def getnext(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> VarBindResult:
    """Return the next OID after the given one (single GETNEXT step)."""
    return asyncio.run(_getnext_with_transport(host, oid, usm, port, timeout, retries))


def walk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> list[VarBindResult]:
    """Traverse the subtree rooted at oid via repeated GETNEXT."""
    return asyncio.run(_walk_with_transport(host, oid, usm, port, timeout, retries))


def bulk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    """GETBULK retrieval."""
    return asyncio.run(
        _bulk_with_transport(host, oid, usm, port, timeout, retries, max_repetitions)
    )


def set_oid(
    host: str,
    oid: str,
    value: str,
    value_type: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> SetResult:
    """Set an OID value. value_type: 'int' | 'str' | 'hex'."""
    if value_type not in ("int", "str", "hex"):
        return {
            "error": f"Unknown type '{value_type}'. Use int, str, or hex.",
            "host": host,
            "oid": oid,
        }

    type_map: dict[str, Any] = {
        "int": lambda: Integer(int(value)),
        "str": lambda: OctetString(value),
        "hex": lambda: OctetString(hexValue=value),
    }
    try:
        snmp_value = type_map[value_type]()
    except (ValueError, TypeError) as exc:
        return {"error": f"Invalid value for type '{value_type}': {exc}", "host": host, "oid": oid}

    return asyncio.run(
        _set_oid_with_transport(host, oid, snmp_value, value, usm, port, timeout, retries)
    )
