# snmpv3-utils — Design Specification

**Date:** 2026-03-20
**Status:** Approved
**License:** MIT

---

## Overview

`snmpv3-utils` is a Python CLI tool for SNMPv3 testing and operations. It fills a gap in the existing tooling landscape where most utilities only support SNMP v1/v2. The tool supports the full SNMPv3 security matrix, all common query and trap operations, credential testing (single and bulk), and named profiles for managing multiple devices and credential sets.

**Target users:** Network engineers and sysadmins who need to test, debug, or automate SNMPv3 interactions from the command line or in scripts/CI pipelines.

**Install:** `pipx install snmpv3-utils`

**Tech stack:** Python, typer, rich, pysnmp 7, python-dotenv, platformdirs, ruff, pytest, mypy, uv

---

## Command Structure

Commands are grouped into four subcommand groups:

```
snmpv3 query get     <host> <oid> [options]
snmpv3 query getnext <host> <oid> [options]
snmpv3 query walk    <host> <oid> [options]
snmpv3 query bulk    <host> <oid> [options]
snmpv3 query set     <host> <oid> <value> --type <int|str|hex> [options]

snmpv3 trap send   <host> [options]
snmpv3 trap listen [options]

snmpv3 auth check  <host> [options]
snmpv3 auth bulk   <host> --file <creds.csv> [options]

snmpv3 profile list
snmpv3 profile add   <name> [options]
snmpv3 profile delete <name>
snmpv3 profile show  <name>
```

**Global flags** (available on all commands):
- `--profile <name>` — load credentials from a named profile
- `--format <rich|json>` — output format (default: `rich`)
- `--timeout <int>` — SNMP timeout in seconds (default: 5)
- `--retries <int>` — number of retries (default: 3)
- `--port <int>` — UDP port (default: 161, 162 for trap listen)

**Credential flags** (override profile/env):
- `--username`
- `--auth-protocol <MD5|SHA1|SHA256|SHA512>`
- `--auth-key`
- `--priv-protocol <DES|AES128|AES256>`
- `--priv-key`
- `--security-level <noAuthNoPriv|authNoPriv|authPriv>`

---

## Project Structure

```
snmpv3-utils/
├── src/
│   └── snmpv3_utils/
│       ├── __init__.py
│       ├── cli/                  # Typer entry points only — no business logic
│       │   ├── main.py           # Root app, registers subcommand groups
│       │   ├── query.py          # snmpv3 query *
│       │   ├── trap.py           # snmpv3 trap *
│       │   ├── auth.py           # snmpv3 auth *
│       │   └── profile.py        # snmpv3 profile *
│       ├── core/                 # All SNMP logic — no CLI or output concerns
│       │   ├── query.py          # get, getnext, walk, bulk, set
│       │   ├── trap.py           # send_trap, listen
│       │   └── auth.py           # check_creds, bulk_check
│       ├── config.py             # Profile loading, .env resolution, platformdirs
│       ├── output.py             # Rich tables and JSON formatting
│       └── security.py           # SNMPv3 USM parameter builder (UsmUserData)
├── tests/
│   ├── fixtures/                 # Sample SNMP responses for consistent test data
│   ├── test_query.py
│   ├── test_trap.py
│   ├── test_auth.py
│   ├── test_config.py
│   ├── test_output.py
│   └── test_security.py
├── docs/
│   └── superpowers/
│       └── specs/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── new_operation.md
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml                # PR: ruff, pytest, mypy
│       └── release.yml           # On tag: build + publish to PyPI via uv
├── pyproject.toml
├── .env.example
├── CLAUDE.md
├── CONTRIBUTING.md
├── CHANGELOG.md
└── README.md
```

---

## Architecture

### Separation of concerns

- `cli/` modules are thin: parse arguments, resolve credentials, call `core/`, pass results to `output.py`. Zero SNMP logic.
- `core/` modules contain all SNMP logic and return plain Python dicts. No rich, no typer, no side effects beyond network calls.
- `security.py` is the single pysnmp-aware module. Everything else receives a `UsmUserData` object.
- `output.py` knows only about dicts and the `--format` flag.

This separation makes `core/` trivially testable without invoking the CLI or a real device.

### Data flow

```
CLI args + env + profile
        |
    config.py  (credential resolution)
        |
    security.py (build UsmUserData)
        |
    core/*.py  (SNMP operation → plain dict)
        |
    output.py  (rich table or JSON → stdout)
```

---

## Credentials & Configuration

### Resolution order (lowest to highest priority)

1. Built-in defaults (port 161, timeout 5, retries 3)
2. Environment variables / `.env` file in current working directory
3. Named profile (`~/.config/snmpv3utils/profiles.toml` on Linux, platform-appropriate via `platformdirs`)
4. CLI flags

### Environment variables (`.env.example`)

```ini
SNMPV3_USERNAME=
SNMPV3_AUTH_PROTOCOL=SHA256       # MD5 | SHA1 | SHA256 | SHA512
SNMPV3_AUTH_KEY=
SNMPV3_PRIV_PROTOCOL=AES128       # DES | AES128 | AES256
SNMPV3_PRIV_KEY=
SNMPV3_SECURITY_LEVEL=authPriv    # noAuthNoPriv | authNoPriv | authPriv
SNMPV3_PORT=161
SNMPV3_TIMEOUT=5
SNMPV3_RETRIES=3
```

### Profiles (`profiles.toml`)

```toml
[profiles.prod-router]
username = "admin"
auth_protocol = "SHA256"
auth_key = "secret"
priv_protocol = "AES128"
priv_key = "secret"
security_level = "authPriv"
port = 161
timeout = 5
retries = 3

[profiles.lab]
username = "testuser"
security_level = "noAuthNoPriv"
```

Profiles support all the same fields as env vars: `username`, `auth_protocol`, `auth_key`, `priv_protocol`, `priv_key`, `security_level`, `port`, `timeout`, `retries`.

Managed via `snmpv3 profile add / delete / list / show`. File lives in the user config directory resolved by `platformdirs` — works correctly after `pipx install`.

### Bulk credential file format (CSV)

```
username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
admin,SHA256,pass1,AES128,pass2,authPriv
monitor,SHA1,pass3,DES,pass4,authPriv
guest,,,,noAuthNoPriv
```

---

## SNMPv3 Security Matrix

`security.py` builds a `UsmUserData` object for every supported combination:

| Security Level  | Auth Protocols         | Priv Protocols      |
|-----------------|------------------------|---------------------|
| noAuthNoPriv    | —                      | —                   |
| authNoPriv      | MD5, SHA1, SHA256, SHA512 | —                |
| authPriv        | MD5, SHA1, SHA256, SHA512 | DES, AES128, AES256 |

`security.py` is the only module that imports from pysnmp's USM API. All other modules call `security.build_usm_user(credentials) -> UsmUserData`.

---

## Operations

| Group   | Command       | Core function                     | Notes |
|---------|---------------|-----------------------------------|-------|
| query   | get           | `get(host, oid, usm)`             | Single OID fetch |
| query   | getnext       | `getnext(host, oid, usm)`         | Single GETNEXT step — returns the next OID after the given one |
| query   | walk          | `walk(host, oid, usm)`            | Full subtree traversal via repeated GETNEXT |
| query   | bulk          | `bulk(host, oid, usm)`            | GETBULK, `--max-repetitions` flag |
| query   | set           | `set(host, oid, val, type, usm)`  | `--type int|str|hex` required |
| trap    | send          | `send_trap(host, usm, inform)`    | Fire-and-forget trap by default; `--inform` sends an INFORM-REQUEST and waits for acknowledgment (different PDU type, requires response from receiver) |
| trap    | listen        | `listen(port, usm)`               | Blocking; decrypts and prints incoming traps for a single credential set. v1 limitation: one USM identity per listener invocation. |
| auth    | check         | `check_creds(host, usm)`          | GET on sysDescr, reports success/fail |
| auth    | bulk          | `bulk_check(host, file)`          | Tests all credential rows in the CSV against a single target host. Multi-host bulk testing is out of scope for v1. |

All core functions return `dict` or `list[dict]`. Errors are returned as dicts with an `error` key, never raised to the CLI layer as unhandled exceptions.

---

## Output

Controlled by global `--format` flag.

**rich (default):** Colored tables via `rich.table`, success/error status badges, progress spinner during long operations (walk, bulk-check, trap listen).

**json:** Plain JSON to stdout, no color. Safe for piping into `jq` or other tools.

---

## Testing Strategy

- **Framework:** `pytest`
- **Mocking boundary:** the pysnmp transport layer (`pysnmp.hlapi` send/receive calls). `core/` tests pass a pre-built `UsmUserData` object directly and mock the transport so no real network call is made. `security.py` has its own isolated unit tests that verify correct `UsmUserData` construction for each protocol combination.
- **Fixtures:** `tests/fixtures/` contains sample raw SNMP responses to ensure consistent test data across platforms.
- **Coverage:** all `core/` and `config.py` functions must have tests before merge. CLI layer tested with typer's test client.
- **TDD:** tests written before implementation for every new operation.

---

## CI/CD

### `ci.yml` (runs on every PR)

1. `uv run ruff check .` — linting
2. `uv run ruff format --check .` — formatting
3. `uv run mypy src/` — type checking
4. `uv run pytest` — full test suite

### `release.yml` (runs on version tag `v*`)

1. Run full CI suite (ruff, mypy, pytest) — publish only if all pass
2. Build package with `uv build`
3. Publish to PyPI (requires `PYPI_TOKEN` secret set in GitHub repository settings)
4. Create a GitHub Release using the tag and the matching `CHANGELOG.md` entry

---

## Collaboration

- **Branch protection:** PRs required to merge to `main`; CI must pass
- **Conventional commits:** enforced; `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com) format and is updated manually on each release using conventional commit history as input
- **Issue templates:** bug report, feature request, new operation
- **PR template:** checklist — tests written, ruff passes, mypy passes, docs updated
- **`CONTRIBUTING.md`:** dev setup with `uv`, running tests, adding a new command
- **`CLAUDE.md`:** AI assistant instructions, project conventions, PR/issue workflow

---

## Future Considerations (out of scope for v1)

- Interactive TUI mode (explore MIB tree interactively)
- MIB file loading and OID name resolution
- SNMPv1/v2c support (lower priority — existing tools cover this)
- Config file watching / daemon mode for trap listener
- Standalone executable packaging (e.g. PyInstaller or Nuitka) for Windows/Linux/macOS — no Python required on target machine
