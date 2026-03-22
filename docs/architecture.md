# Architecture

## Overview

`snmpv3-utils` is a Python CLI tool for SNMPv3 testing. It supports the full SNMPv3 security matrix, all common query and trap operations, credential testing (single and bulk), and named profiles.

**Stack:** Python, typer, rich, pysnmp 7 (lextudio), python-dotenv, platformdirs, ruff, pytest, mypy, uv

## Separation of Concerns

```
CLI args + env + profile
        |
    config.py  (credential resolution)
        |
    security.py (build UsmUserData)
        |
    core/*.py  (SNMP operation → TypedDict result)
        |
    output.py  (rich table or JSON → stdout)
```

| Layer | Responsibility | Rule |
|-------|---------------|------|
| `cli/` | Thin Typer wrappers — parse args, resolve creds, call core, pass to output | No SNMP logic, no pysnmp imports |
| `cli/_options.py` | Shared option type aliases and `build_usm_from_cli` helper | |
| `core/` | All SNMP operations — returns TypedDict results, errors as `{"error": "..."}` | No CLI, no rich |
| `core/query.py` | Async internals (`_get`, `_getnext`, etc.) + `_*_with_transport` wrappers + sync public API via `asyncio.run()` | |
| `core/auth.py` | Credential checking — `_check_creds_async` reuses engine/transport from `_get`; `_bulk_check_async` fans out with `asyncio.gather` + `Semaphore` | |
| `core/trap.py` | `send_trap`, `stress_trap` + future `listen` | |
| `types.py` | All TypedDict definitions and Union aliases | |
| `security.py` | Only file that imports pysnmp auth/priv constants; re-exports `UsmUserData` | |
| `output.py` | Only file that imports rich; takes dicts, formats for display | |
| `config.py` | Profile loading, `.env` resolution, platformdirs paths | |

## Async Architecture

pysnmp v7 is fully async. Core modules use a two-level pattern:

1. **`_get(engine, host, oid, usm, transport)`** — async, accepts pre-built engine/transport for reuse from other async contexts (e.g., `_bulk_check_async`)
2. **`_get_with_transport(host, oid, usm, port, timeout, retries)`** — async, self-contained (creates its own engine/transport)
3. **`get(host, oid, usm, ...)`** — sync public API, calls `asyncio.run(_get_with_transport(...))`

This avoids nested `asyncio.run()` calls while enabling engine/transport reuse for bulk operations.

## Credential Resolution Order

Lowest to highest priority:

1. Built-in defaults (port 161, timeout 5, retries 3)
2. Environment variables / `.env` file
3. Named profile (`profiles.toml` via platformdirs)
4. CLI flags

## SNMPv3 Security Matrix

| Security Level | Auth Protocols | Priv Protocols |
|----------------|----------------|----------------|
| noAuthNoPriv | — | — |
| authNoPriv | MD5, SHA1, SHA256, SHA512 | — |
| authPriv | MD5, SHA1, SHA256, SHA512 | DES, AES128, AES256 |

## Testing

- Mock boundary: pysnmp async functions (`_get_cmd_async`, etc.) using `AsyncMock`
- `core/` tests pass pre-built `UsmUserData` directly
- CLI tests use typer's `CliRunner`
- Concurrency tests verify row-order preservation, semaphore limits, and invalid-row handling

## Known Limitations

- `asyncio.run()` raises `RuntimeError` inside already-running event loops (e.g., Jupyter)
- `trap listen` is not yet implemented (issue #1)
