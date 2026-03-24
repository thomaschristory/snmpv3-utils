# Trap Listener Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `snmpv3 trap listen` — a blocking SNMPv3 trap receiver that prints arriving traps in order, supporting all saved profiles automatically.

**Architecture:** `core/trap.py` gains a real `listen()` implementation using pysnmp v7's asyncio transport dispatcher and `ntfrcv.NotificationReceiver`. `add_transport()` auto-creates and registers an `AsyncioDispatcher` via `UdpAsyncioTransport.PROTO_TRANSPORT_DISPATCHER`; no manual dispatcher creation needed. The CLI conditionally auto-loads all profiles or uses explicit credentials. Output gets a new streaming `print_trap_received()` formatter.

**Tech Stack:** pysnmp 7.x (`ntfrcv.NotificationReceiver`, `UdpAsyncioTransport`, `snmp_config.add_transport`, `snmp_config.add_v3_user`), Typer, Rich.

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `src/snmpv3_utils/types.py` | Modify | Add `TrapReceived` TypedDict |
| `src/snmpv3_utils/__init__.py` | Modify | Export `TrapReceived` |
| `src/snmpv3_utils/output.py` | Modify | Add `print_trap_received()` |
| `src/snmpv3_utils/core/trap.py` | Modify | Implement `listen()`; new imports |
| `src/snmpv3_utils/cli/trap.py` | Modify | New credential-detection branch; new imports |
| `tests/test_types.py` | Modify | Add TrapReceived shape tests |
| `tests/test_output.py` | Modify | Add print_trap_received tests |
| `tests/test_trap.py` | Modify | Add listen() unit tests |
| `tests/test_cli_trap.py` | Modify | Replace stub test; add new listen tests |

---

## Task 1: Add TrapReceived TypedDict

**Files:**
- Modify: `src/snmpv3_utils/types.py`
- Modify: `src/snmpv3_utils/__init__.py`
- Modify: `tests/test_types.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_types.py`:

```python
class TestTrapReceived:
    def test_trap_received_shape(self):
        from snmpv3_utils.types import TrapReceived, VarBindSuccess
        record: TrapReceived = {
            "host": "192.168.1.1",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "12345"}],
        }
        assert record["host"] == "192.168.1.1"
        assert record["timestamp"] == "2026-03-23T12:00:00"
        assert len(record["varbinds"]) == 1
        assert record["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.3.0"

    def test_trap_received_exported_from_package(self):
        from snmpv3_utils import TrapReceived
        assert TrapReceived is not None
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
uv run pytest tests/test_types.py::TestTrapReceived -v
```

Expected: `ImportError: cannot import name 'TrapReceived'`

- [ ] **Step 3: Add TrapReceived to types.py**

In `src/snmpv3_utils/types.py`, after the `TrapResult` alias, add:

```python
# --- Trap listener operation ---


class TrapReceived(TypedDict):
    host: str
    timestamp: str  # ISO-8601, e.g. "2026-03-23T12:34:56"
    varbinds: list[VarBindSuccess]
```

- [ ] **Step 4: Export TrapReceived from __init__.py**

In `src/snmpv3_utils/__init__.py`, add `TrapReceived` to both the import and `__all__`:

```python
from snmpv3_utils.types import (
    AuthError,
    AuthResult,
    AuthSuccess,
    SetError,
    SetResult,
    SetSuccess,
    TrapError,
    TrapReceived,
    TrapResult,
    TrapSuccess,
    VarBindError,
    VarBindResult,
    VarBindSuccess,
)

__all__ = [
    "AuthError",
    "AuthResult",
    "AuthSuccess",
    "SetError",
    "SetResult",
    "SetSuccess",
    "TrapError",
    "TrapReceived",
    "TrapResult",
    "TrapSuccess",
    "VarBindError",
    "VarBindResult",
    "VarBindSuccess",
]
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run pytest tests/test_types.py::TestTrapReceived -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
uv run pytest
```

Expected: all existing tests pass plus the new ones.

- [ ] **Step 7: Commit**

```bash
git add src/snmpv3_utils/types.py src/snmpv3_utils/__init__.py tests/test_types.py
git commit -m "feat: add TrapReceived TypedDict and export from package"
```

---

## Task 2: Add print_trap_received to output.py

**Files:**
- Modify: `src/snmpv3_utils/output.py`
- Modify: `tests/test_output.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_output.py`:

```python
class TestPrintTrapReceived:
    def test_rich_output_contains_host_and_timestamp(self):
        from io import StringIO
        from rich.console import Console
        from snmpv3_utils.output import OutputFormat, print_trap_received

        record = {
            "host": "10.0.0.1",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "12345"}],
        }
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        print_trap_received(record, fmt=OutputFormat.RICH, console=console)
        output = buf.getvalue()
        assert "10.0.0.1" in output
        assert "2026-03-23T12:00:00" in output
        assert "1.3.6.1.2.1.1.3.0" in output
        assert "12345" in output

    def test_rich_output_with_multiple_varbinds(self):
        from io import StringIO
        from rich.console import Console
        from snmpv3_utils.output import OutputFormat, print_trap_received

        record = {
            "host": "10.0.0.2",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [
                {"oid": "1.3.6.1.2.1.1.3.0", "value": "999"},
                {"oid": "1.3.6.1.6.3.1.1.4.1.0", "value": "1.3.6.1.6.3.1.1.5.1"},
            ],
        }
        buf = StringIO()
        console = Console(file=buf, highlight=False)
        print_trap_received(record, fmt=OutputFormat.RICH, console=console)
        output = buf.getvalue()
        assert "1.3.6.1.2.1.1.3.0" in output
        assert "1.3.6.1.6.3.1.1.4.1.0" in output

    def test_json_output_is_valid_json_with_correct_keys(self):
        import json
        from unittest.mock import patch
        from snmpv3_utils.output import OutputFormat, print_trap_received

        record = {
            "host": "10.0.0.3",
            "timestamp": "2026-03-23T12:00:00",
            "varbinds": [{"oid": "1.3.6.1.2.1.1.3.0", "value": "0"}],
        }
        with patch("builtins.print") as mock_print:
            print_trap_received(record, fmt=OutputFormat.JSON)
        printed = mock_print.call_args[0][0]
        parsed = json.loads(printed)
        assert parsed["host"] == "10.0.0.3"
        assert parsed["timestamp"] == "2026-03-23T12:00:00"
        assert isinstance(parsed["varbinds"], list)
        assert parsed["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.3.0"

    def test_json_output_with_empty_varbinds(self):
        import json
        from unittest.mock import patch
        from snmpv3_utils.output import OutputFormat, print_trap_received

        record = {"host": "10.0.0.4", "timestamp": "2026-03-23T12:00:00", "varbinds": []}
        with patch("builtins.print") as mock_print:
            print_trap_received(record, fmt=OutputFormat.JSON)
        printed = mock_print.call_args[0][0]
        parsed = json.loads(printed)
        assert parsed["varbinds"] == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_output.py::TestPrintTrapReceived -v
```

Expected: `ImportError: cannot import name 'print_trap_received'`

- [ ] **Step 3: Implement print_trap_received in output.py**

Add to `src/snmpv3_utils/output.py` (before `print_error`):

```python
def print_trap_received(
    record: Mapping[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a single received trap. Called once per arriving trap (streaming).

    Rich: header line with timestamp and host, then OID/Value table.
    JSON: one JSON object per line, newline-delimited.
    """
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _default_console
    c.print(f"[bold]{record['timestamp']}[/bold] Trap from [cyan]{record['host']}[/cyan]")
    varbinds = record.get("varbinds", [])
    if varbinds:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("OID")
        table.add_column("Value")
        for vb in varbinds:
            table.add_row(str(vb["oid"]), str(vb["value"]))
        c.print(table)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_output.py::TestPrintTrapReceived -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/output.py tests/test_output.py
git commit -m "feat: add print_trap_received streaming formatter"
```

---

## Task 3: Implement core listen()

**Files:**
- Modify: `src/snmpv3_utils/core/trap.py`
- Modify: `tests/test_trap.py`

### pysnmp v7 dispatcher notes

`snmp_config.add_transport()` auto-creates and registers an `AsyncioDispatcher` when `engine.transport_dispatcher is None`, by calling `engine.register_transport_dispatcher(transport.PROTO_TRANSPORT_DISPATCHER())`. `UdpAsyncioTransport.PROTO_TRANSPORT_DISPATCHER` is `AsyncioDispatcher`. Do NOT manually assign `engine.transport_dispatcher` — that bypasses the required `register_recv_callback` / `register_timer_callback` wiring. After `add_transport()`, access the dispatcher via `engine.transport_dispatcher`.

`AsyncioDispatcher.run_dispatcher()` calls `loop.run_forever()` directly — no `job_started()` call is needed.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_trap.py` (at the top of the file, add `from unittest.mock import MagicMock` if not already present):

```python
class TestListen:
    def test_listen_raises_value_error_on_empty_users(self):
        from snmpv3_utils.core.trap import listen
        with pytest.raises(ValueError, match="users list must not be empty"):
            listen(16299, [], on_trap=lambda r: None)

    @patch("snmpv3_utils.core.trap.snmp_config.add_v3_user")
    @patch("snmpv3_utils.core.trap.snmp_config.add_transport")
    @patch("snmpv3_utils.core.trap.ntfrcv.NotificationReceiver")
    @patch("snmpv3_utils.core.trap.SnmpEngine")
    def test_listen_calls_on_trap_with_correct_shape(
        self, mock_engine_cls, mock_ntfrcv, mock_add_transport, mock_add_v3_user
    ):
        captured = {}

        def capture_ntfrcv(engine, cb):
            captured["cb"] = cb
            return MagicMock()

        mock_ntfrcv.side_effect = capture_ntfrcv

        def fake_run_dispatcher():
            mock_oid = MagicMock()
            mock_oid.__str__ = lambda self: "1.3.6.1.2.1.1.3.0"
            mock_val = MagicMock()
            mock_val.__str__ = lambda self: "12345"
            captured["cb"](MagicMock(), "ref1", b"", b"", [(mock_oid, mock_val)], None)

        mock_engine_cls.return_value.transport_dispatcher.run_dispatcher.side_effect = (
            fake_run_dispatcher
        )

        received = []
        usm = MagicMock()
        from snmpv3_utils.core.trap import listen
        listen(16299, [usm], on_trap=received.append)

        assert len(received) == 1
        record = received[0]
        assert "host" in record
        assert "timestamp" in record
        assert "varbinds" in record
        assert isinstance(record["varbinds"], list)
        assert len(record["varbinds"]) == 1
        assert record["varbinds"][0]["oid"] == "1.3.6.1.2.1.1.3.0"
        assert record["varbinds"][0]["value"] == "12345"

    @patch("snmpv3_utils.core.trap.snmp_config.add_v3_user")
    @patch("snmpv3_utils.core.trap.snmp_config.add_transport")
    @patch("snmpv3_utils.core.trap.ntfrcv.NotificationReceiver")
    @patch("snmpv3_utils.core.trap.SnmpEngine")
    def test_listen_registers_all_usm_users(
        self, mock_engine_cls, mock_ntfrcv, mock_add_transport, mock_add_v3_user
    ):
        mock_engine_cls.return_value.transport_dispatcher.run_dispatcher.return_value = None

        usm1 = MagicMock()
        usm1.userName = "alice"
        usm2 = MagicMock()
        usm2.userName = "bob"

        from snmpv3_utils.core.trap import listen
        listen(16299, [usm1, usm2], on_trap=None)

        assert mock_add_v3_user.call_count == 2
        names_registered = [call.args[1] for call in mock_add_v3_user.call_args_list]
        assert "alice" in names_registered
        assert "bob" in names_registered

    @patch("snmpv3_utils.core.trap.snmp_config.add_v3_user")
    @patch("snmpv3_utils.core.trap.snmp_config.add_transport")
    @patch("snmpv3_utils.core.trap.ntfrcv.NotificationReceiver")
    @patch("snmpv3_utils.core.trap.SnmpEngine")
    def test_listen_exits_cleanly_on_keyboard_interrupt(
        self, mock_engine_cls, mock_ntfrcv, mock_add_transport, mock_add_v3_user
    ):
        mock_engine_cls.return_value.transport_dispatcher.run_dispatcher.side_effect = (
            KeyboardInterrupt
        )

        usm = MagicMock()
        from snmpv3_utils.core.trap import listen
        listen(16299, [usm], on_trap=None)  # must not raise

        mock_engine_cls.return_value.transport_dispatcher.close_dispatcher.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_trap.py::TestListen -v
```

Expected: `NotImplementedError` from the stub.

- [ ] **Step 3: Implement listen() in core/trap.py**

Add new imports at the top of `src/snmpv3_utils/core/trap.py` (after the existing imports block):

```python
from datetime import datetime

from pysnmp.carrier.asyncio.dgram import udp as udp_transport
from pysnmp.entity import config as snmp_config
from pysnmp.entity.rfc3413 import ntfrcv
```

Update the `from snmpv3_utils.types import ...` line to include `TrapReceived`:

```python
from snmpv3_utils.types import StressResult, TrapReceived, TrapResult
```

Replace the `listen()` stub (the entire function starting at `def listen(`) with:

```python
def listen(
    port: int,
    users: list[UsmUserData],
    on_trap: Callable[[TrapReceived], None] | None = None,
) -> None:
    """Block and receive incoming SNMPv3 traps, calling on_trap for each one.

    users: one UsmUserData per SNMPv3 credential set to accept; all are
           registered with the engine so traps from any of them are decrypted.
    on_trap: called with a TrapReceived dict for each arriving trap.
             If None, traps are silently dropped.

    Blocks until KeyboardInterrupt. Binds to 0.0.0.0:<port>.
    Raises ValueError if users is empty.
    """
    if not users:
        raise ValueError("users list must not be empty")

    logger.info("LISTEN port=%d users=%d", port, len(users))

    engine = SnmpEngine()

    # Register all USM users so the engine can authenticate/decrypt their traps
    for usm in users:
        snmp_config.add_v3_user(
            engine,
            usm.userName,
            authProtocol=usm.authentication_protocol,
            authKey=usm.authentication_key,
            privProtocol=usm.privacy_protocol,
            privKey=usm.privacy_key,
        )

    # add_transport auto-creates and registers an AsyncioDispatcher via
    # UdpAsyncioTransport.PROTO_TRANSPORT_DISPATCHER when transport_dispatcher is None.
    # Do NOT pre-assign engine.transport_dispatcher — that bypasses register_recv_callback.
    snmp_config.add_transport(
        engine,
        udp_transport.DOMAIN_NAME,
        udp_transport.UdpAsyncioTransport().open_server_mode(("0.0.0.0", port)),
    )

    # Capture the source IP via observer before the ntfrcv callback fires.
    # The "rfc3412.prepareDataElements:unconfirmed" execpoint fires for incoming
    # unconfirmed PDUs (traps) and includes transportAddress = (host, port).
    _current_host: dict[str, str] = {"value": "unknown"}

    def _store_transport(
        snmpEngine: SnmpEngine,
        execpoint: str,
        variables: dict[str, Any],
        cbCtx: Any,
    ) -> None:
        addr = variables.get("transportAddress")
        if addr is not None:
            try:
                _current_host["value"] = str(addr[0])
            except (IndexError, TypeError):
                pass

    engine.observer.register_observer(
        _store_transport, "rfc3412.prepareDataElements:unconfirmed"
    )

    def _callback(
        snmpEngine: SnmpEngine,
        stateReference: Any,
        contextEngineId: Any,
        contextName: Any,
        varBinds: Any,
        cbCtx: Any,
    ) -> None:
        host = _current_host["value"]
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        varbinds: list[dict[str, str]] = [
            {"oid": str(oid), "value": str(val)} for oid, val in varBinds
        ]
        record: TrapReceived = {"host": host, "timestamp": timestamp, "varbinds": varbinds}
        if on_trap:
            on_trap(record)

    ntfrcv.NotificationReceiver(engine, _callback)

    try:
        engine.transport_dispatcher.run_dispatcher()
    except KeyboardInterrupt:
        pass
    finally:
        engine.transport_dispatcher.close_dispatcher()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_trap.py::TestListen -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest
```

Expected: all pass.

- [ ] **Step 6: Run lint and type check**

```bash
uv run ruff check src/snmpv3_utils/core/trap.py
uv run mypy src/
```

Fix any issues before committing.

- [ ] **Step 7: Commit**

```bash
git add src/snmpv3_utils/core/trap.py tests/test_trap.py
git commit -m "feat: implement trap listener with asyncio notification receiver"
```

---

## Task 4: Update CLI listen command

**Files:**
- Modify: `src/snmpv3_utils/cli/trap.py`
- Modify: `tests/test_cli_trap.py`

- [ ] **Step 1: Remove old stub test and write new failing tests**

In `tests/test_cli_trap.py`, remove the `TestTrapListen` class entirely (it tests `NotImplementedError` behaviour that is now gone). Then add:

```python
class TestTrapListen:
    @patch("snmpv3_utils.cli.trap.core_listen")
    @patch("snmpv3_utils.cli.trap.config.list_profiles")
    def test_no_credentials_no_profiles_exits_1(self, mock_list, mock_listen):
        mock_list.return_value = []
        result = runner.invoke(app, ["trap", "listen", "--port", "16299"])
        assert result.exit_code != 0
        mock_listen.assert_not_called()

    @patch("snmpv3_utils.cli.trap.core_listen")
    @patch("snmpv3_utils.cli.trap.build_usm_user")
    @patch("snmpv3_utils.cli.trap.config.load_profile")
    @patch("snmpv3_utils.cli.trap.config.list_profiles")
    def test_no_credentials_loads_all_profiles(
        self, mock_list, mock_load, mock_usm, mock_listen
    ):
        from snmpv3_utils.security import Credentials

        mock_list.return_value = ["alice", "bob"]
        mock_load.return_value = Credentials(username="alice")
        mock_usm.return_value = object()
        mock_listen.return_value = None

        result = runner.invoke(app, ["trap", "listen", "--port", "16299"])

        assert mock_load.call_count == 2
        assert mock_listen.called
        call_args = mock_listen.call_args
        users_arg = call_args.kwargs.get("users") or call_args.args[1]
        assert len(users_arg) == 2

    @patch("snmpv3_utils.cli.trap.core_listen")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_explicit_profile_uses_single_user(self, mock_usm, mock_creds, mock_listen):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials(username="alice")
        mock_usm.return_value = object()
        mock_listen.return_value = None

        result = runner.invoke(
            app, ["trap", "listen", "--port", "16299", "--profile", "alice"]
        )

        assert mock_listen.called
        call_args = mock_listen.call_args
        users_arg = call_args.kwargs.get("users") or call_args.args[1]
        assert len(users_arg) == 1

    @patch("snmpv3_utils.cli.trap.core_listen")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_inline_credentials_uses_single_user(self, mock_usm, mock_creds, mock_listen):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials(username="admin")
        mock_usm.return_value = object()
        mock_listen.return_value = None

        result = runner.invoke(
            app, ["trap", "listen", "--port", "16299", "--username", "admin"]
        )

        assert mock_listen.called
        call_args = mock_listen.call_args
        users_arg = call_args.kwargs.get("users") or call_args.args[1]
        assert len(users_arg) == 1
```

- [ ] **Step 2: Run new tests to confirm they fail**

```bash
uv run pytest tests/test_cli_trap.py::TestTrapListen -v
```

Expected: failures (CLI still uses old unconditional path).

- [ ] **Step 3: Update cli/trap.py imports**

Replace the imports block at the top of `src/snmpv3_utils/cli/trap.py` with:

```python
# src/snmpv3_utils/cli/trap.py
"""CLI commands for snmpv3 trap *."""

from typing import Annotated

import typer

from snmpv3_utils import config
from snmpv3_utils.cli._options import (
    AuthKeyOpt,
    AuthProtoOpt,
    FormatOpt,
    PortOpt,
    PrivKeyOpt,
    PrivProtoOpt,
    ProfileOpt,
    RetriesOpt,
    SecLevelOpt,
    TimeoutOpt,
    UsernameOpt,
    build_usm_from_cli,
)
from snmpv3_utils.core.trap import listen as core_listen
from snmpv3_utils.core.trap import send_trap as core_send_trap
from snmpv3_utils.core.trap import stress_trap as core_stress_trap
from snmpv3_utils.debug import translate_error
from snmpv3_utils.output import OutputFormat, print_error, print_single, print_trap_received, stress_progress
from snmpv3_utils.security import build_usm_user
```

- [ ] **Step 4: Replace the listen command function**

In `src/snmpv3_utils/cli/trap.py`, replace the entire `listen` function (from `@app.command()` before `def listen(` to the `except KeyboardInterrupt` block) with:

```python
@app.command()
def listen(
    port: Annotated[int, typer.Option("--port", help="UDP port to listen on")] = 162,
    profile: ProfileOpt = None,
    username: UsernameOpt = None,
    auth_protocol: AuthProtoOpt = None,
    auth_key: AuthKeyOpt = None,
    priv_protocol: PrivProtoOpt = None,
    priv_key: PrivKeyOpt = None,
    security_level: SecLevelOpt = None,
    fmt: FormatOpt = OutputFormat.RICH,
) -> None:
    """Listen for incoming SNMPv3 traps (blocking).

    With no credential flags: decrypts traps from all saved profiles.
    With --profile or inline flags: uses only those credentials.
    Press Ctrl+C to stop.
    """
    any_cred = any(
        x is not None
        for x in [
            profile,
            username,
            auth_protocol,
            auth_key,
            priv_protocol,
            priv_key,
            security_level,
        ]
    )

    if any_cred:
        usm, _creds = build_usm_from_cli(
            profile,
            username,
            auth_protocol,
            auth_key,
            priv_protocol,
            priv_key,
            security_level,
            port=None,
            timeout=None,
            retries=None,
        )
        users = [usm]
    else:
        names = config.list_profiles()
        if not names:
            typer.echo(
                "Error: no profiles saved and no credentials provided. "
                "Use --username or save a profile first.",
                err=True,
            )
            raise typer.Exit(1)
        users = [build_usm_user(config.load_profile(name)) for name in names]

    typer.echo(f"Listening for SNMPv3 traps on port {port}... (Ctrl+C to stop)")
    try:
        core_listen(port, users=users, on_trap=lambda r: print_trap_received(r, fmt=fmt))
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
```

- [ ] **Step 5: Run new tests to confirm they pass**

```bash
uv run pytest tests/test_cli_trap.py::TestTrapListen -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest
```

Expected: all pass.

- [ ] **Step 7: Run lint and type check**

```bash
uv run ruff check src/snmpv3_utils/cli/trap.py
uv run mypy src/
```

Fix any issues.

- [ ] **Step 8: Commit**

```bash
git add src/snmpv3_utils/cli/trap.py tests/test_cli_trap.py
git commit -m "feat: update trap listen CLI with auto-profile loading"
```

---

## Task 5: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run lint and type check**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
```

Fix any issues.

- [ ] **Step 3: Smoke test the CLI help**

```bash
uv run snmpv3 trap listen --help
```

Expected: shows `--port`, `--profile`, `--username`, credential options. No errors.

- [ ] **Step 4: Commit any final fixes**

If there were fixes in step 2:

```bash
git add -p
git commit -m "fix: address lint/type issues in trap listener"
```
