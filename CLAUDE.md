# CLAUDE.md

Project instructions for AI assistants working on snmpv3-utils.

## Setup

```bash
uv sync --all-extras
```

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy src/` |
| Run CLI | `uv run snmpv3 --help` |

## Architecture Rules

- **`cli/`** — thin Typer wrappers only. No SNMP logic, no direct pysnmp imports.
- **`core/`** — all SNMP operations. Returns `dict` or `list[dict]`. No CLI, no rich.
- **`security.py`** — the only file that imports pysnmp auth/priv constants.
- **`output.py`** — the only file that imports rich. Takes dicts, formats for display.

## Adding a New Operation

1. Write the failing test in `tests/test_<module>.py`
2. Implement in `core/<module>.py`
3. Add the CLI command in `cli/<module>.py`
4. Add a CLI test using typer's `CliRunner`
5. Open an issue, work in a branch, open a PR

## PR & Issue Workflow

- All work starts with a GitHub Issue
- Branch from `main`, name: `feat/<issue-number>-<short-description>`
- PRs require CI to pass (ruff, mypy, pytest)
- Conventional commits required: `feat:`, `fix:`, `docs:`, `chore:`, `test:`

## pysnmp v7 Notes

- Import from `pysnmp.hlapi.v3arch.asyncio` (NOT `pysnmp.hlapi` — that's v6)
- Auth constants: `usmHMACMD5AuthProtocol`, `usmHMACSHAAuthProtocol`, `usmHMAC192SHA256AuthProtocol`, `usmHMAC384SHA512AuthProtocol`
- Priv constants: `usmDESPrivProtocol`, `usmAesCfb128Protocol`, `usmAesCfb256Protocol`
- All SNMP operations are async in v7 — core/ wraps them with `asyncio.run()`
- Trap listener requires asyncio (v7 removed asyncore dispatcher) — see `core/trap.py`

## Session Guidelines

- **Save state to memory** after completing each major task (PR merged, feature implemented, review done, etc.) and before ending a session. Update the project memory file with: merged PRs, new issues, architecture changes, and any decisions made. Don't wait until the end — context can get large and compress, losing details.
