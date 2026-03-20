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

# ---------------------------------------------------------------------------
# Sync wrappers around the async pysnmp v7 API.
# These names are patched in tests, so they must be module-level names.
# ---------------------------------------------------------------------------

def getCmd(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    *var_binds: ObjectType,
    **options: Any,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sync wrapper: run async get_cmd via asyncio.run()."""
    result = asyncio.run(_get_cmd_async(engine, usm, transport, context, *var_binds, **options))
    return [result]


def nextCmd(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    *var_binds: ObjectType,
    **options: Any,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sync wrapper: run async next_cmd via asyncio.run()."""
    result = asyncio.run(_next_cmd_async(engine, usm, transport, context, *var_binds, **options))
    return [result]


def setCmd(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    *var_binds: ObjectType,
    **options: Any,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sync wrapper: run async set_cmd via asyncio.run()."""
    result = asyncio.run(_set_cmd_async(engine, usm, transport, context, *var_binds, **options))
    return [result]


def walkCmd(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    var_bind: ObjectType,
    **options: Any,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sync wrapper: collect all results from async walk_cmd generator."""
    async def _collect() -> list[tuple[Any, Any, Any, Any]]:
        results = []
        async for item in _walk_cmd_async(engine, usm, transport, context, var_bind, **options):
            results.append(item)
        return results

    return asyncio.run(_collect())


def bulkCmd(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    non_repeaters: int,
    max_repetitions: int,
    *var_binds: ObjectType,
    **options: Any,
) -> list[tuple[Any, Any, Any, Any]]:
    """Sync wrapper: run async bulk_cmd via asyncio.run()."""
    result = asyncio.run(
        _bulk_cmd_async(
            engine, usm, transport, context,
            non_repeaters, max_repetitions,
            *var_binds, **options,
        )
    )
    return [result]


# ---------------------------------------------------------------------------
# Transport helper
# ---------------------------------------------------------------------------

def _transport(host: str, port: int, timeout: int, retries: int) -> UdpTransportTarget:
    return asyncio.run(
        UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    )


# ---------------------------------------------------------------------------
# Var-bind helper
# ---------------------------------------------------------------------------

def _var_bind_to_dict(var_bind: Any) -> dict[str, Any]:
    return {"oid": var_bind[0].prettyPrint(), "value": var_bind[1].prettyPrint()}


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
) -> dict[str, Any]:
    """Fetch a single OID value."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, var_binds in getCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return _var_bind_to_dict(var_binds[0])
    return {"error": "No response", "host": host, "oid": oid}


def getnext(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> dict[str, Any]:
    """Return the next OID after the given one (single GETNEXT step)."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, var_binds in nextCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return _var_bind_to_dict(var_binds[0])
    return {"error": "No response", "host": host, "oid": oid}


def walk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Traverse the subtree rooted at oid via repeated GETNEXT."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    results = []
    for error_indication, error_status, _, var_binds in walkCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append({"error": str(error_indication or error_status)})
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


def bulk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
    max_repetitions: int = 25,
) -> list[dict[str, Any]]:
    """GETBULK retrieval."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    results = []
    for error_indication, error_status, _, var_binds in bulkCmd(
        engine, usm, transport, ContextData(),
        0, max_repetitions,
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append({"error": str(error_indication or error_status)})
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


def set_oid(
    host: str,
    oid: str,
    value: str,
    value_type: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> dict[str, Any]:
    """Set an OID value. value_type: 'int' | 'str' | 'hex'."""
    if value_type not in ("int", "str", "hex"):
        return {"error": f"Unknown type '{value_type}'. Use int, str, or hex."}

    type_map: dict[str, Any] = {
        "int": lambda: Integer(int(value)),
        "str": lambda: OctetString(value),
        "hex": lambda: OctetString(hexValue=value),
    }
    snmp_value = type_map[value_type]()

    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, _ in setCmd(
        engine, usm, transport, ContextData(),
        ObjectType(ObjectIdentity(oid), snmp_value),
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return {"status": "ok", "host": host, "oid": oid, "value": value}
    return {"error": "No response", "host": host, "oid": oid}
