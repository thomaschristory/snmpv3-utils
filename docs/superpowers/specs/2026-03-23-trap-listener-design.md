# Trap Listener Design

**Date:** 2026-03-23
**Issue:** #1 — feat: implement trap listen (asyncio notification receiver)

## Summary

Implement the `snmpv3 trap listen` command, which blocks and prints incoming SNMPv3 traps as they arrive. The `listen()` stub in `core/trap.py` raises `NotImplementedError`; this spec covers replacing it with a working asyncio implementation.

---

## Requirements

- SNMPv3 only (no v1/v2c)
- Blocking — runs until Ctrl+C
- Prints traps in arrival order, one entry per trap (all varbinds bundled)
- Supports multiple simultaneous USM users (one per saved profile by default)
- If explicit credentials are given (`--profile` or inline), use those only
- If no credentials are given, auto-load all saved profiles

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

---

## Core: `core/trap.py`

### Signature change

```python
# Before (stub)
def listen(port: int, usm: UsmUserData, on_trap: ...) -> None

# After
def listen(port: int, users: list[UsmUserData], on_trap: ...) -> None
```

### Implementation

- Create `SnmpEngine`
- Register all `UsmUserData` entries as USM users on the engine via pysnmp v7 config API
- Bind a UDP transport on `('0.0.0.0', port)` using pysnmp v7 asyncio transport
- Register a notification receiver callback via `ntfrcv.NotificationReceiver`
- In the callback: collect all varbinds, build a `TrapReceived` dict, call `on_trap`
- Run the asyncio event loop until `KeyboardInterrupt`, then close the dispatcher cleanly

All asyncio interaction stays inside `listen()`; callers see a blocking synchronous function (consistent with `stress_trap`).

---

## CLI: `cli/trap.py`

Update the existing `listen` command:

- Credential args (`--profile`, `--username`, etc.) become fully optional
- If any credential arg is provided: build a single USM user (existing `build_usm_from_cli` path)
- If no credential arg is provided: call `config.load_all_profiles()`, build a `UsmUserData` per profile. If no profiles exist, print an error and exit 1.
- Pass `users: list[UsmUserData]` to `core_listen`
- Ctrl+C is caught in the CLI and prints `"\nStopped."` (already in place)

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

- **Rich**: header line `[timestamp] Trap from <host>`, then a two-column table (OID / Value), one row per varbind. Same `bold cyan` header style as existing tables.
- **JSON**: `print(json.dumps(record))` — newline-delimited, one object per trap, pipeable.

---

## Testing

### `tests/test_trap.py`
- `listen()` calls `on_trap` with correct `TrapReceived` shape when callback fires
- All USM users in `users` list are registered on the engine
- `listen()` exits cleanly on `KeyboardInterrupt`
- Empty `users` list raises `ValueError`

### `tests/test_cli_trap.py`
- No credentials + no saved profiles → exit 1 with error message
- No credentials + saved profiles → all profiles loaded, `core_listen` called with list
- `--profile NAME` given → single USM user passed
- Inline credentials given → single USM user passed

### `tests/test_output.py`
- `print_trap_received` rich output contains host, timestamp, OID, value
- `print_trap_received` JSON output is valid JSON with correct keys

All tests use mocks — no real UDP socket required.

---

## Out of Scope

- SNMPv1/v2c community trap support
- MIB resolution (OIDs printed as numeric strings)
- Multiple simultaneous ports
- Filtering by OID or source host
