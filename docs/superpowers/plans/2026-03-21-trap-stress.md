# Trap Stress Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `snmpv3 trap stress <host>` command that sends high-volume traps for load testing SNMP receivers.

**Architecture:** New async orchestrator (`_stress_loop`) dispatches concurrent `_send_one` tasks via `asyncio.gather` with semaphore-based concurrency control and rate limiting. Sync public API wraps with `asyncio.run()`. CLI provides Rich progress bar or JSON output.

**Tech Stack:** pysnmp 7 (async send_notification), asyncio (gather, Semaphore), typer, rich (Progress)

**Spec:** `docs/superpowers/specs/2026-03-21-trap-stress-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/snmpv3_utils/types.py` | Modify | Add `StressResult` TypedDict |
| `src/snmpv3_utils/core/trap.py` | Modify | Add `_send_one`, `_stress_loop`, `stress_trap`; fix `listen()` docstring |
| `src/snmpv3_utils/cli/trap.py` | Modify | Add `stress` command with progress bar |
| `tests/test_trap.py` | Modify | Add `TestStressTrap` class with core tests |
| `tests/test_cli_trap.py` | Modify | Add `TestTrapStress` class with CLI tests |

---

### Task 1: Add `StressResult` TypedDict + ensure `pytest-asyncio`

**Files:**
- Modify: `src/snmpv3_utils/types.py:75` (append after `TrapResult`)

- [ ] **Step 1: Ensure `pytest-asyncio` is in dev dependencies**

The async tests in Task 2 require `pytest-asyncio`. Check `pyproject.toml` for it; if missing:

```bash
uv add --dev pytest-asyncio
```

- [ ] **Step 2: Add StressResult to types.py**

```python
# --- Stress test operation ---


class StressResult(TypedDict):
    host: str
    sent: int
    errors: int
    success_rate: str
    duration_s: float
    rate_achieved: float
    error_samples: list[str]
```

- [ ] **Step 3: Run type check**

Run: `uv run mypy src/snmpv3_utils/types.py`
Expected: PASS, no errors

- [ ] **Step 4: Commit**

```bash
git add src/snmpv3_utils/types.py
git commit -m "feat(types): add StressResult TypedDict (#4)"
```

---

### Task 2: Add `_send_one` async helper + tests

**Files:**
- Modify: `src/snmpv3_utils/core/trap.py` (add after `send_trap`, before `listen`)
- Modify: `tests/test_trap.py` (add `TestSendOne` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_trap.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest


class TestSendOne:
    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_none_on_success(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, None, None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result is None
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_error_indication(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = ("RequestTimedOut", None, None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result == "RequestTimedOut"

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_error_status(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, "genErr", None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result == "genErr"

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_passes_inform_type(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, None, None, [])
        sem = asyncio.Semaphore(10)
        await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=True, sem=sem,
        )
        call_args = mock_send.call_args
        assert call_args[0][4] == "inform"
```

Add `import asyncio` at the top of `tests/test_trap.py` (it is not currently imported).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_trap.py::TestSendOne -v`
Expected: FAIL — `_send_one` does not exist yet

- [ ] **Step 3: Implement `_send_one`**

Add to `src/snmpv3_utils/core/trap.py` after the `send_trap` function (before `listen`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_trap.py::TestSendOne -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/trap.py tests/test_trap.py
git commit -m "feat(trap): add _send_one async helper (#4)"
```

---

### Task 3: Add `_stress_loop` and `stress_trap` + core tests

**Files:**
- Modify: `src/snmpv3_utils/core/trap.py` (add after `_send_one`, before `listen`)
- Modify: `tests/test_trap.py` (add `TestStressTrap` class)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_trap.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock


class TestStressTrap:
    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_count_mode_sends_correct_number(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["sent"] == 10
        assert result["errors"] == 0
        assert result["host"] == "192.168.1.1"
        assert mock_send.call_count == 10

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_error_counting(self, mock_send, mock_transport):
        # 7 success, 3 errors
        side_effects = [(None, None, None, [])] * 7 + [("timeout", None, None, [])] * 3
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["sent"] == 10
        assert result["errors"] == 3

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_success_rate_calculation(self, mock_send, mock_transport):
        side_effects = [(None, None, None, [])] * 8 + [("err", None, None, [])] * 2
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["success_rate"] == "80.0%"

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_error_samples_dedup_keeps_first_five(self, mock_send, mock_transport):
        # 8 unique error messages
        side_effects = [(f"error_{i}", None, None, []) for i in range(8)]
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=8, rate=0)
        assert len(result["error_samples"]) == 5
        assert result["error_samples"] == ["error_0", "error_1", "error_2", "error_3", "error_4"]

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_zero_count_no_division_error(self, mock_send, mock_transport):
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=0, rate=0)
        assert result["sent"] == 0
        assert result["success_rate"] == "N/A"
        assert result["rate_achieved"] == 0.0
        mock_send.assert_not_called()

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_result_shape(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=1, rate=0)
        expected_keys = {"host", "sent", "errors", "success_rate", "duration_s", "rate_achieved", "error_samples"}
        assert set(result.keys()) == expected_keys

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_on_progress_callback_called(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        progress_calls = []
        stress_trap(
            "192.168.1.1", usm=MagicMock(), count=5, rate=0,
            on_progress=lambda dispatched, total: progress_calls.append((dispatched, total)),
        )
        assert len(progress_calls) == 5
        assert progress_calls[0] == (1, 5)
        assert progress_calls[-1] == (5, 5)

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_concurrency_limits_inflight(self, mock_send, mock_transport):
        """Verify semaphore limits concurrent in-flight sends."""
        max_concurrent_seen = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        original_return = (None, None, None, [])

        async def _slow_send(*args, **kwargs):
            nonlocal max_concurrent_seen, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent_seen:
                    max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return original_return

        mock_send.side_effect = _slow_send
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0, concurrency=3)
        assert result["sent"] == 10
        assert max_concurrent_seen <= 3

    @patch("snmpv3_utils.core.trap.time")
    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_duration_mode_stops_after_elapsed(self, mock_send, mock_transport, mock_time):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        # Calls: start=0.0, loop check=0.0 (dispatch 1), loop check=0.5 (dispatch 2),
        # loop check=1.5 (stop), elapsed=1.5
        mock_time.monotonic.side_effect = [0.0, 0.0, 0.5, 1.5, 1.5]
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=1000, duration=1, rate=0)
        assert result["sent"] == 2  # only 2 dispatched before time exceeded
```

Add this import at the top of the test file:

```python
from snmpv3_utils.core.trap import stress_trap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_trap.py::TestStressTrap -v`
Expected: FAIL — `stress_trap` does not exist yet

- [ ] **Step 3: Implement `_stress_loop` and `stress_trap`**

Add `import time` to the imports at top of `src/snmpv3_utils/core/trap.py`.

Add `StressResult` to the import from `snmpv3_utils.types`:

```python
from snmpv3_utils.types import StressResult, TrapResult
```

Add after `_send_one`, before `listen`:

```python
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
    transport = await UdpTransportTarget.create(
        (host, port), timeout=timeout, retries=retries
    )
    sem = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[str | None]] = []
    interval = 1.0 / rate if rate > 0 else 0
    total = count if duration is None else None
    start = time.monotonic()

    if duration is not None:
        # Duration mode: loop until time exceeds duration
        while time.monotonic() - start < duration:
            tasks.append(
                asyncio.create_task(
                    _send_one(engine, usm, transport, oid, inform, sem)
                )
            )
            if on_progress:
                on_progress(len(tasks), total)
            if interval:
                await asyncio.sleep(interval)
    else:
        # Count mode: dispatch exactly `count` tasks
        for _ in range(count):
            tasks.append(
                asyncio.create_task(
                    _send_one(engine, usm, transport, oid, inform, sem)
                )
            )
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
        if isinstance(r, Exception):
            error_list.append(str(r))
        elif r is not None:
            error_list.append(r)

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
            host, usm, count, duration, rate, concurrency,
            inform, port, timeout, retries, oid, on_progress,
        )
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_trap.py::TestStressTrap -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Run full test suite + linting**

Run: `uv run pytest && uv run ruff check . && uv run mypy src/`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/types.py src/snmpv3_utils/core/trap.py tests/test_trap.py
git commit -m "feat(trap): add stress_trap core with async orchestrator (#4)"
```

---

### Task 4: Fix stale `listen()` docstring

**Files:**
- Modify: `src/snmpv3_utils/core/trap.py:134-137`

- [ ] **Step 1: Update the docstring and error message**

In `listen()`, replace:

```python
    raise NotImplementedError(
        "Trap listener requires pysnmp v7 asyncio integration. "
        "See docs/superpowers/specs/2026-03-20-snmpv3-utils-design.md for context."
    )
```

With:

```python
    raise NotImplementedError(
        "Trap listener requires pysnmp v7 asyncio integration. "
        "See docs/architecture.md for context."
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/snmpv3_utils/core/trap.py
git commit -m "fix(trap): update listen() docstring to reference architecture.md (#4)"
```

---

### Task 5: Add `stress` CLI command + tests

**Files:**
- Modify: `src/snmpv3_utils/cli/trap.py` (add `stress` command after `listen`)
- Modify: `tests/test_cli_trap.py` (add `TestTrapStress` class)

- [ ] **Step 1: Write the failing CLI tests**

Add to `tests/test_cli_trap.py`:

```python
import json


class TestTrapStress:
    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_json_output(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "192.168.1.1",
            "sent": 10,
            "errors": 1,
            "success_rate": "90.0%",
            "duration_s": 1.5,
            "rate_achieved": 6.7,
            "error_samples": ["timeout"],
        }

        result = runner.invoke(
            app, ["trap", "stress", "192.168.1.1", "--count", "10", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["sent"] == 10
        assert data["errors"] == 1
        assert "success_rate" in data

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_0_on_partial_success(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h", "sent": 10, "errors": 5,
            "success_rate": "50.0%", "duration_s": 1.0,
            "rate_achieved": 10.0, "error_samples": [],
        }

        result = runner.invoke(
            app, ["trap", "stress", "h", "--count", "10", "--format", "json"]
        )
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_1_on_all_errors(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h", "sent": 10, "errors": 10,
            "success_rate": "0.0%", "duration_s": 1.0,
            "rate_achieved": 10.0, "error_samples": ["err"],
        }

        result = runner.invoke(
            app, ["trap", "stress", "h", "--count", "10", "--format", "json"]
        )
        assert result.exit_code == 1

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_1_on_zero_sent(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h", "sent": 0, "errors": 0,
            "success_rate": "N/A", "duration_s": 0.0,
            "rate_achieved": 0.0, "error_samples": [],
        }

        result = runner.invoke(
            app, ["trap", "stress", "h", "--count", "0", "--format", "json"]
        )
        assert result.exit_code == 1

```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_trap.py::TestTrapStress -v`
Expected: FAIL — `stress` command and `core_stress_trap` import don't exist in CLI yet

- [ ] **Step 3: Implement the `stress` CLI command**

Add import at top of `src/snmpv3_utils/cli/trap.py`:

```python
from snmpv3_utils.core.trap import stress_trap as core_stress_trap
```

Add after the `listen` command:

```python
@app.command()
def stress(
    host: str,
    count: Annotated[int, typer.Option("--count", "-n", help="Total traps to send")] = 1000,
    duration: Annotated[
        int | None, typer.Option("--duration", "-d", help="Run for N seconds (overrides --count)")
    ] = None,
    rate: Annotated[int, typer.Option("--rate", help="Target traps/sec (0=unlimited)")] = 100,
    concurrency: Annotated[
        int, typer.Option("--concurrency", help="Max concurrent in-flight traps")
    ] = 10,
    inform: Annotated[
        bool, typer.Option("--inform", help="Send INFORM-REQUEST (acknowledged)")
    ] = False,
    oid: Annotated[str, typer.Option("--oid", help="Trap OID")] = "1.3.6.1.6.3.1.1.5.1",
    port: PortOpt = None,
    timeout: TimeoutOpt = None,
    retries: RetriesOpt = None,
    profile: ProfileOpt = None,
    username: UsernameOpt = None,
    auth_protocol: AuthProtoOpt = None,
    auth_key: AuthKeyOpt = None,
    priv_protocol: PrivProtoOpt = None,
    priv_key: PrivKeyOpt = None,
    security_level: SecLevelOpt = None,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """Send a high volume of traps for stress testing.

    By default sends 1000 traps at 100/s with concurrency=10.
    Use --duration to run for a fixed time instead of a fixed count.
    """
    usm, creds = build_usm_from_cli(
        profile,
        username,
        auth_protocol,
        auth_key,
        priv_protocol,
        priv_key,
        security_level,
        port,
        timeout,
        retries,
    )

    # Build progress callback for Rich mode
    progress_callback = None
    progress = None
    task_id = None
    if fmt == OutputFormat.RICH:
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}" if duration is None else "{task.completed} sent"),
            TextColumn("[green]{task.fields[rate]}/s"),
        )
        total_val = count if duration is None else None
        task_id = progress.add_task(
            f"Stress testing {host}", total=total_val, rate="0"
        )

        start_time = __import__("time").monotonic()

        def _on_progress(dispatched: int, total: int | None) -> None:
            elapsed = __import__("time").monotonic() - start_time
            current_rate = f"{dispatched / elapsed:.1f}" if elapsed > 0 else "0"
            progress.update(task_id, completed=dispatched, rate=current_rate)

        progress_callback = _on_progress

    # Use retries=0 default for stress unless explicitly overridden
    stress_retries = creds.retries if retries is not None else 0

    if progress:
        progress.start()
    try:
        result = core_stress_trap(
            host,
            usm,
            count=count,
            duration=duration,
            rate=rate,
            concurrency=concurrency,
            inform=inform,
            port=creds.port,
            timeout=creds.timeout,
            retries=stress_retries,
            oid=oid,
            on_progress=progress_callback,
        )
    finally:
        if progress:
            progress.stop()

    if result["sent"] > 0 and result["errors"] < result["sent"]:
        print_single(result, fmt=fmt)
    else:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
```

- [ ] **Step 4: Run CLI tests to verify they pass**

Run: `uv run pytest tests/test_cli_trap.py::TestTrapStress -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full test suite + linting**

Run: `uv run pytest && uv run ruff check . && uv run mypy src/`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/cli/trap.py tests/test_cli_trap.py
git commit -m "feat(cli): add trap stress command with progress bar (#4)"
```

---

### Task 6: Final validation

- [ ] **Step 1: Run full CI suite locally**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -v
```

Expected: All pass, no warnings

- [ ] **Step 2: Verify CLI help**

```bash
uv run snmpv3 trap stress --help
```

Expected: Shows all options with descriptions

- [ ] **Step 3: Squash or combine commits if desired, then push**

```bash
git push origin main
```

Or create a feature branch + PR per project workflow:

```bash
git checkout -b feat/4-trap-stress
git push -u origin feat/4-trap-stress
gh pr create --title "feat: trap stress test mode (#4)" --body "..."
```
