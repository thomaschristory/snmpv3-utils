# Trap Stress Test — Design Specification

**Date:** 2026-03-21
**Issue:** #4
**Status:** Approved

---

## Overview

Add `snmpv3 trap stress <host>` — a high-volume trap sender for load/stress testing SNMP receivers. Measures throughput, error rate, and receiver behavior under pressure.

## Types — `types.py`

```python
class StressResult(TypedDict):
    host: str
    sent: int
    errors: int
    success_rate: str        # "99.7%" or "N/A" if sent=0
    duration_s: float
    rate_achieved: float     # 0.0 if sent=0
    error_samples: list[str] # first 5 unique error strings (insertion-order dedup)
```

## Core — `core/trap.py`

Import `StressResult` from `snmpv3_utils.types`.

### `_send_one(engine, usm, transport, oid, inform, sem) -> str | None`

Async. Acquires semaphore, calls `_async_send_notification` with the full pysnmp signature:

```python
async def _send_one(engine, usm, transport, oid, inform, sem):
    async with sem:
        error_indication, error_status, _, _ = await _async_send_notification(
            engine, usm, transport, ContextData(),
            "inform" if inform else "trap",
            NotificationType(ObjectIdentity(oid)),
        )
        if error_indication:
            return str(error_indication)
        if error_status:
            return str(error_status)
        return None
```

Uses the pre-built `transport` passed in — no per-send `await UdpTransportTarget.create()`.

### `_stress_loop(host, usm, count, duration, rate, concurrency, inform, port, timeout, retries, oid, on_progress) -> StressResult`

Async orchestrator:

1. Creates one `SnmpEngine` and one `UdpTransportTarget` (via `await UdpTransportTarget.create()`). Note: `_make_udp_target` is the sync constructor used by `send_trap`; stress uses the async constructor since it's already in an async context.
2. Creates `asyncio.Semaphore(concurrency)`
3. Loops, creating tasks — passes the shared `engine` to each `_send_one` call:
   - **Count mode** (`duration is None`): loop `count` times
   - **Duration mode** (`duration is not None`): loop until `time.monotonic() - start >= duration`, ignore `count`
4. Rate limiting: `await asyncio.sleep(1/rate)` between task creation. This throttles the *dispatch rate*, not execution — the semaphore independently caps concurrency. Together they approximate the target rate. `rate=0` skips sleep (unlimited).
5. Calls `on_progress(dispatched, total)` after each task creation. `dispatched` is tasks created so far, `total` is `count` in count mode or `None` in duration mode. This tracks dispatch progress, not completion.
6. `await asyncio.gather(*tasks, return_exceptions=True)` — waits for all in-flight tasks to complete
7. Counts completed tasks as `sent` (= len(tasks)), errors from non-None results. Builds `StressResult`.

**Edge case — zero sent:** If `count=0` or duration expires before any task fires, return `StressResult` with `sent=0`, `errors=0`, `success_rate="N/A"`, `rate_achieved=0.0`.

**Error samples:** Collect unique error strings in insertion order (use `dict.fromkeys()` pattern), keep first 5.

### `stress_trap(host, usm, ..., on_progress=None) -> StressResult`

Sync public API. Calls `asyncio.run(_stress_loop(...))`.

Parameters:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `host` | required | Target host |
| `usm` | required | Pre-built `UsmUserData` |
| `count` | 1000 | Total traps (count mode) |
| `duration` | `None` | Seconds to run (duration mode, overrides count) |
| `rate` | 100 | Target traps/sec, 0 = unlimited |
| `concurrency` | 10 | Max in-flight traps (semaphore) |
| `inform` | `False` | INFORM-REQUEST vs fire-and-forget |
| `port` | 162 | Target UDP port |
| `timeout` | 5 | Per-trap timeout |
| `retries` | 0 | Default 0 for stress (don't retry during flood) |
| `oid` | `1.3.6.1.6.3.1.1.5.1` | coldStart |
| `on_progress` | `None` | `Callable[[int, int \| None], None]` — `(dispatched, total)` |

### Fix stale docstring

`listen()` references the deleted spec file — update to reference `docs/architecture.md`.

## CLI — `cli/trap.py`

New `stress` command:

```
snmpv3 trap stress <host> [options]
```

Options mirror the core parameters plus standard credential options from `_options.py`.

`--count` and `--duration` are mutually exclusive (use typer callback validation).

**Rich mode:** `rich.progress.Progress` bar showing `dispatched/total` (count mode) or `dispatched` with elapsed time (duration mode). After completion, prints `StressResult` via `print_single`.

**JSON mode:** No progress output. Prints final `StressResult` dict.

**Exit code:** 0 if `sent > 0 and errors < sent` (at least one success), 1 if all failed or zero sent.

## Testing

Mock boundary: `snmpv3_utils.core.trap._async_send_notification` with `AsyncMock`.

### Core tests (`tests/test_trap.py`)

1. **Count mode basic**: `stress_trap(count=10, rate=0)` — assert 10 calls to `_async_send_notification`, result shape correct
2. **Error counting**: some sends return error indication — assert `errors` field matches
3. **Success rate calculation**: mix of success/error — verify percentage string
4. **Error samples dedup**: >5 unique errors — only first 5 unique kept (insertion order)
5. **Rate=0**: no sleep, all sends fire immediately
6. **Concurrency**: mock with delay, verify semaphore limits concurrent calls
7. **Duration mode**: mock `time.monotonic` to simulate elapsed time, verify loop stops after duration
8. **Zero sent**: `count=0` — verify `success_rate="N/A"`, no division by zero

### CLI tests (`tests/test_cli_trap.py`)

1. **JSON output**: mock `stress_trap`, invoke with `--format json`, verify parseable JSON with correct keys
2. **Exit code 0**: at least one success
3. **Exit code 1**: all errors
4. **Mutually exclusive options**: `--count` + `--duration` together → error

## Files Changed

| File | Change |
|------|--------|
| `types.py` | Add `StressResult` TypedDict |
| `core/trap.py` | Add `_send_one`, `_stress_loop`, `stress_trap`; fix `listen()` docstring; add `StressResult` import |
| `cli/trap.py` | Add `stress` command with progress bar |
| `tests/test_trap.py` | Add stress core tests |
| `tests/test_cli_trap.py` | Add stress CLI tests |
