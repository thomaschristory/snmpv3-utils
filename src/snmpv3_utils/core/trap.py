# src/snmpv3_utils/core/trap.py
"""Trap send and receive operations.

send_trap: fire-and-forget (trap) or acknowledged (inform, --inform flag).
listen: blocking trap receiver for a single USM credential set.
stress_trap: send a high volume of traps for load testing.

Note on trap listener: pysnmp v7 uses asyncio for its notification receiver.
The synchronous ntfrcv API was removed. The listen() function is a stub
pending asyncio implementation.
"""

import asyncio
import time
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

from snmpv3_utils.types import StressResult, TrapResult


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
    result = asyncio.run(
        _async_send_notification(
            engine,
            usm,
            transport,
            context,
            notification_type,
            notification,
        )
    )
    return [result]


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
) -> TrapResult:
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
            return {
                "error": str(error_indication),
                "host": host,
                "type": notification_type,
                "inform": inform,
            }
        if error_status:
            return {
                "error": str(error_status),
                "host": host,
                "type": notification_type,
                "inform": inform,
            }
        return {"status": "ok", "host": host, "type": notification_type, "inform": inform}

    return {"error": "No response", "host": host, "type": notification_type, "inform": inform}


async def _send_one(
    engine: SnmpEngine,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    oid: str,
    inform: bool,
    sem: asyncio.Semaphore,
) -> str | None:
    """Send a single trap/inform under semaphore control.

    Returns error string on failure, None on success.
    """
    async with sem:
        error_indication, error_status, _, _ = await _async_send_notification(
            engine,
            usm,
            transport,
            ContextData(),
            "inform" if inform else "trap",
            NotificationType(ObjectIdentity(oid)),
        )
        if error_indication:
            return str(error_indication)
        if error_status:
            return str(error_status)
        return None


_MAX_ERROR_SAMPLES = 5


async def _stress_loop(
    host: str,
    usm: UsmUserData,
    count: int,
    duration: int | None,
    rate: int,
    concurrency: int,
    inform: bool,
    port: int,
    timeout: int,
    retries: int,
    oid: str,
    on_progress: Callable[[int, int | None], None] | None,
) -> StressResult:
    """Async orchestrator for stress testing.

    Count mode (duration=None): dispatch exactly `count` traps.
    Duration mode (duration set): dispatch until elapsed >= duration seconds.
    """
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, port), timeout=timeout, retries=retries)
    sem = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[str | None]] = []
    interval = 1.0 / rate if rate > 0 else 0
    total = count if duration is None else None
    start = time.monotonic()

    if duration is not None:
        # Duration mode: loop until time exceeds duration
        while time.monotonic() - start < duration:
            tasks.append(asyncio.create_task(_send_one(engine, usm, transport, oid, inform, sem)))
            if on_progress:
                on_progress(len(tasks), total)
            if interval:
                await asyncio.sleep(interval)
    else:
        # Count mode: dispatch exactly `count` tasks
        for _ in range(count):
            tasks.append(asyncio.create_task(_send_one(engine, usm, transport, oid, inform, sem)))
            if on_progress:
                on_progress(len(tasks), total)
            if interval:
                await asyncio.sleep(interval)

    if not tasks:
        return StressResult(
            host=host,
            sent=0,
            errors=0,
            success_rate="N/A",
            duration_s=round(time.monotonic() - start, 2),
            rate_achieved=0.0,
            error_samples=[],
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.monotonic() - start
    sent = len(results)

    # Collect errors: non-None strings or exceptions
    error_list: list[str] = []
    for r in results:
        if isinstance(r, BaseException):
            error_list.append(str(r))
        elif r is not None:
            error_list.append(str(r))

    errors = len(error_list)
    # Dedup keeping insertion order, take first 5
    unique_errors = list(dict.fromkeys(error_list))[:_MAX_ERROR_SAMPLES]

    return StressResult(
        host=host,
        sent=sent,
        errors=errors,
        success_rate=f"{(sent - errors) / sent * 100:.1f}%" if sent > 0 else "N/A",
        duration_s=round(elapsed, 2),
        rate_achieved=round(sent / elapsed, 1) if elapsed > 0 else 0.0,
        error_samples=unique_errors,
    )


def stress_trap(
    host: str,
    usm: UsmUserData,
    count: int = 1000,
    duration: int | None = None,
    rate: int = 100,
    concurrency: int = 10,
    inform: bool = False,
    port: int = 162,
    timeout: int = 5,
    retries: int = 0,
    oid: str = "1.3.6.1.6.3.1.1.5.1",
    on_progress: Callable[[int, int | None], None] | None = None,
) -> StressResult:
    """Send a high volume of traps for stress testing.

    count: total traps to send (count mode, ignored if duration is set).
    duration: run for N seconds (duration mode, overrides count).
    rate: target traps/sec dispatch rate (0 = unlimited).
    concurrency: max concurrent in-flight traps via semaphore.
    on_progress: callback(dispatched, total) called after each task dispatch.
    """
    return asyncio.run(
        _stress_loop(
            host,
            usm,
            count,
            duration,
            rate,
            concurrency,
            inform,
            port,
            timeout,
            retries,
            oid,
            on_progress,
        )
    )


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
        "See docs/architecture.md for context."
    )
