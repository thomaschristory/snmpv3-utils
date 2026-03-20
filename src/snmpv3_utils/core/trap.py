# src/snmpv3_utils/core/trap.py
"""Trap send and receive operations.

send_trap: fire-and-forget (trap) or acknowledged (inform, --inform flag).
listen: blocking trap receiver for a single USM credential set.

Note on trap listener: pysnmp v7 uses asyncio for its notification receiver.
The synchronous ntfrcv API was removed. The listen() function is a stub
pending asyncio implementation.
"""
import asyncio
from collections.abc import Callable
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    ContextData,
    NotificationType,
    ObjectIdentity,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
)
from pysnmp.hlapi.v3arch.asyncio import (
    send_notification as _async_send_notification,
)


def sendNotification(  # noqa: N802  (matches pysnmp camelCase convention)
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    context: ContextData,
    notification_type: str,
    notification: NotificationType,
) -> list[tuple[Any, Any, Any, Any]]:
    """Synchronous wrapper around pysnmp v7's async send_notification.

    Returns a list of (errorIndication, errorStatus, errorIndex, varBinds)
    tuples, matching the old synchronous hlapi iterator contract so that
    send_trap can iterate over results with a plain for-loop.
    """
    return asyncio.run(
        _async_send_notification(
            engine,
            usm,
            transport,
            context,
            notification_type,
            notification,
        )
    )


def _make_udp_target(host: str, port: int, timeout: int, retries: int) -> UdpTransportTarget:
    """Construct a UdpTransportTarget synchronously.

    pysnmp v7 moved DNS resolution into an async .create() classmethod, but
    the underlying object still supports synchronous construction when
    transport_address is set before __init__ is called.  This helper sets
    transport_address on the bare instance before delegating to __init__,
    which avoids the async DNS lookup while keeping the object fully formed.
    """
    target = UdpTransportTarget.__new__(UdpTransportTarget)
    target.transport_address = (host, port)
    target.__init__(timeout=timeout, retries=retries)
    return target


def send_trap(
    host: str,
    usm: UsmUserData,
    inform: bool = False,
    port: int = 162,
    timeout: int = 5,
    retries: int = 3,
    oid: str = "1.3.6.1.6.3.1.1.5.1",  # coldStart
) -> dict[str, Any]:
    """Send an SNMPv3 trap or inform.

    inform=False: fire-and-forget (no acknowledgment expected).
    inform=True:  INFORM-REQUEST — waits for acknowledgment from receiver.
    """
    engine = SnmpEngine()
    transport = _make_udp_target(host, port, timeout, retries)
    notification_type = "inform" if inform else "trap"

    for error_indication, error_status, _, _ in sendNotification(
        engine,
        usm,
        transport,
        ContextData(),
        notification_type,
        NotificationType(ObjectIdentity(oid)),
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "type": notification_type}
        if error_status:
            return {"error": str(error_status), "host": host, "type": notification_type}
        return {"status": "ok", "host": host, "type": notification_type, "inform": inform}

    return {"error": "No response", "host": host}


def listen(
    port: int,
    usm: UsmUserData,
    on_trap: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Block and receive incoming SNMPv3 traps, calling on_trap for each one.

    v1 limitation: single USM credential set per invocation.

    pysnmp v7 removed the synchronous asyncore dispatcher.
    This function requires asyncio integration — see pysnmp lextudio docs
    for the asyncio-based notification receiver (ntfrcv) implementation.

    on_trap: called with a dict {"host": ..., "oid": ..., "value": ...} per received var-bind.
             If None, traps are printed to stdout.
    """
    raise NotImplementedError(
        "Trap listener requires pysnmp v7 asyncio integration. "
        "See docs/superpowers/specs/2026-03-20-snmpv3-utils-design.md for context."
    )
