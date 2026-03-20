# Contributing to snmpv3-utils

Thank you for contributing! This guide covers everything you need to get started.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `brew install uv`)
- [GitHub CLI](https://cli.github.com/) (`gh`) for issue/PR management

## Dev Setup

```bash
git clone https://github.com/<your-username>/snmpv3-utils
cd snmpv3-utils
uv sync --all-extras
```

Verify everything works:
```bash
uv run pytest
uv run snmpv3 --help
```

## Workflow

1. **Find or create a GitHub Issue** for the work you want to do
2. **Branch:** `git checkout -b feat/<issue-number>-short-description`
3. **Write tests first** — we use TDD; tests live in `tests/`
4. **Implement** — keep `cli/` thin and business logic in `core/`
5. **Run checks locally** before pushing:
   ```bash
   uv run ruff check . && uv run ruff format . && uv run mypy src/ && uv run pytest
   ```
6. **Commit** using conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
7. **Open a PR** and reference the issue with `Closes #<number>`

## Adding a New SNMP Operation

1. Add the core function in `src/snmpv3_utils/core/<module>.py` — return `dict`/`list[dict]`
2. Add the CLI command in `src/snmpv3_utils/cli/<module>.py` — thin wrapper only
3. Write tests for both in `tests/`
4. Update `README.md` with usage example

## Code Style

- Formatter + linter: `ruff` (configured in `pyproject.toml`)
- Type checker: `mypy --strict`
- No classes unless clearly warranted — prefer functions
- Docstrings on all public functions (one-liner is fine if self-evident)
