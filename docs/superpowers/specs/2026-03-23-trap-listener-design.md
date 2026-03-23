# Trap Listener Design

**Date:** 2026-03-23
**Issue:** #1 — feat: implement trap listen (asyncio notification receiver)

## Summary

Implement the `snmpv3 trap listen` command, which blocks and prints incoming SNMPv3 traps as they arrive. The `listen()` stub in `core/trap.py` raises `NotImplementedError`; this spec covers replacing it with a working asyncio implementation.

---

## Requirements

- SNMPv3 only (no v1/v2c)
- Blocking — runs until Ctrl+C
- Prints traps in arrival order, one entry per trap (all varbinds bundled), printed immediately
- Supports multiple simultaneous USM users (one per saved profile by default)
- If explicit credentials are given (`--profile` or any inline credential option), use those only
- If no credentials are given, auto-load all saved profiles; error and exit 1 if no profiles exist

---

## Architecture

Follows the existing module split:

| Layer | File | Responsibility |
|-------|------|----------------|
| Core | `core/trap.py` | asyncio notification receiver loop |
| CLI | `cli/trap.py` | thin Typer wrapper, credential resolution |
| Types | `types.py` | `TrapReceived` TypedDict |
| Output | `output.py` | `print_trap_received()` formatter |

---

## Data Model

New TypedDict in `types.py`:

```python
class TrapReceived(TypedDict):
    host: str
    timestamp: str          # ISO-8601, e.g. "2026-03-23T12:34:56"
    varbinds: list[VarBindSuccess]   # [{"oid": str, "value": str}, ...]
```

`VarBindSuccess` is already defined in `types.py` and is reused here.

**`username` is intentionally absent** from `TrapReceived`. The received USM username is not surfaced in v1; it can be added in a future iteration.

**`trap_oid` is intentionally absent** as a top-level field. The trap OID (`snmpTrapOID.0`) is always present in `varbinds` as a regular entry per RFC 3416.

**`TrapReceived` must be added to `__init__.py`** alongside the other trap types (`TrapSuccess`, `TrapError`, etc.) so it is part of the public API.

---

## Core: `core/trap.py`

### Signature change

```python
# Before (current stub)
def listen(
    port: int,
    usm: UsmUserData,
    on_trap: Callable[[dict[str, Any]], None] | None = None,
) -> None

# After
def listen(
    port: int,
    users: list[UsmUserData],
    on_trap: Callable[[TrapReceived], None] | None = None,
) -> None
```

`TrapReceived` must be added to the import from `snmpv3_utils.types` (currently `core/trap.py` only imports `StressResult` and `TrapResult`).

`users` must be non-empty; raise `ValueError("users list must not be empty")` if it is. The CLI guards against no-profiles before calling `listen()`, so `ValueError` is only reachable by programmatic API callers.

### Implementation

- Create `SnmpEngine`
- Register all `UsmUserData` entries from `users` as USM users on the engine via pysnmp v7 config API
- Bind a UDP transport on `('0.0.0.0', port)` using pysnmp v7 asyncio transport
- Register a notification receiver callback via `ntfrcv.NotificationReceiver`
- In the callback: collect all varbinds, build a `TrapReceived` dict, call `on_trap`
- Run the asyncio event loop until `KeyboardInterrupt`, then close the dispatcher cleanly

All asyncio interaction stays inside `listen()`; callers see a blocking synchronous function (consistent with `stress_trap`).

---

## CLI: `cli/trap.py`

### New imports required

Add to `cli/trap.py`:
```python
from snmpv3_utils import config
from snmpv3_utils.security import build_usm_user
```

Update the existing output import line to include `print_trap_received`:
```python
from snmpv3_utils.output import OutputFormat, print_error, print_single, print_trap_received, stress_progress
```

### Credential detection — new conditional logic

The current `listen` command unconditionally calls `build_usm_from_cli`. This is replaced with a branch:

**"Any credential arg is provided"** means: any of `profile`, `username`, `auth_protocol`, `auth_key`, `priv_protocol`, `priv_key`, or `security_level` is not `None`.

- **Credential arg provided**: call `build_usm_from_cli(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port=None, timeout=None, retries=None)` (port/timeout/retries are `None`, same as today's unconditional call), pass `[usm]` to `core_listen`.
- **No credential arg provided**:
  1. Call `config.list_profiles()` to get all profile names.
  2. If the list is empty: print an error and `raise typer.Exit(1)` — do NOT call `core_listen`.
  3. For each name: call `config.load_profile(name)` to get a `Credentials` object, then call `build_usm_user(creds)` to convert to `UsmUserData`. Do NOT use `build_usm_from_cli` here — it re-runs env-var resolution and expects raw CLI option values.
  4. Pass the collected `users: list[UsmUserData]` to `core_listen`.

### Other changes

- Replace `on_trap=lambda r: print_single(r, fmt=fmt)` with `on_trap=lambda r: print_trap_received(r, fmt=fmt)`.
- `--port` stays (default 162).
- `--format` stays.
- Ctrl+C caught, prints `"\nStopped."` (already in place).

---

## Output: `output.py`

New function:

```python
def print_trap_received(
    record: TrapReceived,
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None
```

**Rich**: This is a new streaming pattern — unlike `print_single` / `print_records` (which format a single batch), this is called once per arriving trap and writes immediately. For each trap: print a free-text header line `[timestamp] Trap from <host>`, followed by a two-column Rich table (OID / Value) with one row per varbind, using the same `bold cyan` header style as existing tables. Each trap is a self-contained block; no batching across traps.

**JSON**: `print(json.dumps(record))` — newline-delimited, one JSON object per trap, written to stdout immediately on arrival. Pipeable.

---

## Testing

### `tests/test_trap.py`
- `listen()` calls `on_trap` with correct `TrapReceived` shape when receiver callback fires
- All `UsmUserData` entries in `users` list are registered on the engine
- `listen()` exits cleanly on `KeyboardInterrupt`
- `listen()` raises `ValueError` on empty `users` list

### `tests/test_cli_trap.py`
- **Remove or replace** `test_listen_exits_nonzero_with_not_implemented_message` — it tests the old stub behaviour.
- No credentials + no saved profiles → exit 1 with error; mock `snmpv3_utils.cli.trap.config.list_profiles` to return `[]`, verify `core_listen` not called.
- No credentials + saved profiles → `core_listen` called with full `users` list; mock `snmpv3_utils.cli.trap.config.list_profiles` and `snmpv3_utils.cli.trap.config.load_profile`.
- `--profile NAME` given → single-element `users` list passed to `core_listen`.
- Inline credentials given → single-element `users` list passed to `core_listen`.

### `tests/test_output.py`
- `print_trap_received` rich output contains host, timestamp, OID, value.
- `print_trap_received` JSON output is valid JSON with keys `host`, `timestamp`, `varbinds`.

All tests use mocks — no real UDP socket required.

---

## Out of Scope

- SNMPv1/v2c community trap support
- MIB resolution (OIDs printed as numeric strings)
- Multiple simultaneous ports
- Filtering by OID or source host
- Surfacing the received USM `username` in `TrapReceived` (future iteration)
