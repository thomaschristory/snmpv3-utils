# Verbose & Debug Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `-v`/`-vv` verbose flags and smarter SNMP error messages to snmpv3-utils so users can diagnose authentication and protocol issues without Wireshark.

**Architecture:** New `debug.py` module at package root owns logging setup and error translation. Core modules use stdlib `logging` only. CLI layer calls `translate_error()` before `print_error()`. All debug output goes to stderr.

**Tech Stack:** Python stdlib `logging`, Typer `count=True` option, pysnmp `debug` module (lazy import at `-vv`)

**Spec:** `docs/superpowers/specs/2026-03-22-verbose-debugging-design.md`
**Issue:** #36

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/snmpv3_utils/debug.py` | Logging config, USM report OID map, `translate_error()` |
| Create | `tests/test_debug.py` | Tests for debug module |
| Modify | `src/snmpv3_utils/cli/main.py` | Add `-v`/`--verbose` flag to callback |
| Modify | `src/snmpv3_utils/cli/query.py` | Call `translate_error()` on errors |
| Modify | `src/snmpv3_utils/cli/auth.py` | Call `translate_error()` on errors |
| Modify | `src/snmpv3_utils/cli/trap.py` | Call `translate_error()` on errors |
| Modify | `src/snmpv3_utils/core/query.py` | Add `logging.getLogger(__name__)` INFO/DEBUG calls |
| Modify | `src/snmpv3_utils/core/auth.py` | Add `logging.getLogger(__name__)` INFO/DEBUG calls |
| Modify | `src/snmpv3_utils/core/trap.py` | Add `logging.getLogger(__name__)` INFO/DEBUG calls |
| Modify | `tests/test_cli_query.py` | Add CLI tests for `-v`/`-vv` flags |

---

### Task 1: Create `debug.py` with `configure_logging()`

**Files:**
- Create: `src/snmpv3_utils/debug.py`
- Create: `tests/test_debug.py`

- [ ] **Step 1: Write failing tests for `configure_logging()`**

```python
# tests/test_debug.py
import logging

from snmpv3_utils.debug import configure_logging


class TestConfigureLogging:
    def teardown_method(self):
        """Remove handlers added during tests."""
        logger = logging.getLogger("snmpv3_utils")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

    def test_no_verbosity_sets_warning(self):
        configure_logging(0)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.WARNING

    def test_single_v_sets_info(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.INFO

    def test_double_v_sets_debug(self):
        configure_logging(2)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.DEBUG

    def test_handler_writes_to_stderr(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert len(logger.handlers) == 1
        import sys
        assert logger.handlers[0].stream is sys.stderr

    def test_idempotent_no_duplicate_handlers(self):
        configure_logging(1)
        configure_logging(2)
        logger = logging.getLogger("snmpv3_utils")
        assert len(logger.handlers) == 1

    def test_vv_enables_pysnmp_debug(self):
        from unittest.mock import patch

        with patch("snmpv3_utils.debug.set_logger") as mock_set:
            configure_logging(2)
            mock_set.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_debug.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'snmpv3_utils.debug'`

- [ ] **Step 3: Implement `configure_logging()`**

```python
# src/snmpv3_utils/debug.py
"""Verbose/debug output and SNMP error translation.

This module owns logging configuration, the USM report OID hint map,
and error translation. It is the only module that knows about verbosity
levels and error hint logic.
"""

from __future__ import annotations

import logging
import sys

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snmpv3_utils.security import Credentials

_LOGGER_NAME = "snmpv3_utils"


def configure_logging(verbosity: int) -> None:
    """Configure the snmpv3_utils root logger based on verbosity level.

    0 = WARNING (default), 1 = INFO (-v), 2 = DEBUG (-vv).
    Idempotent — safe to call multiple times.
    """
    logger = logging.getLogger(_LOGGER_NAME)

    level_map = {0: logging.WARNING, 1: logging.INFO}
    logger.setLevel(level_map.get(verbosity, logging.DEBUG))

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if verbosity >= 2:
            fmt = "%(levelname)s [%(name)s]: %(message)s"
        else:
            fmt = "%(levelname)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    if verbosity >= 2:
        from pysnmp.debug import Debug, set_logger

        set_logger(Debug("all"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_debug.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run linting and type checking**

Run: `uv run ruff check src/snmpv3_utils/debug.py tests/test_debug.py && uv run mypy src/snmpv3_utils/debug.py`

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/debug.py tests/test_debug.py
git commit -m "feat(debug): add configure_logging with verbosity levels

Part of #36"
```

---

### Task 2: Add `USM_REPORT_HINTS` and `translate_error()`

**Files:**
- Modify: `src/snmpv3_utils/debug.py`
- Modify: `tests/test_debug.py`

- [ ] **Step 1: Write failing tests for `translate_error()`**

Append to `tests/test_debug.py`:

```python
from snmpv3_utils.debug import USM_REPORT_HINTS, translate_error
from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel


class TestUsmReportHints:
    def test_contains_all_six_usm_oids(self):
        expected_oids = [
            "1.3.6.1.6.3.15.1.1.1.0",
            "1.3.6.1.6.3.15.1.1.2.0",
            "1.3.6.1.6.3.15.1.1.3.0",
            "1.3.6.1.6.3.15.1.1.4.0",
            "1.3.6.1.6.3.15.1.1.5.0",
            "1.3.6.1.6.3.15.1.1.6.0",
        ]
        for oid in expected_oids:
            assert oid in USM_REPORT_HINTS


class TestTranslateError:
    def test_known_error_appends_hint(self):
        result = translate_error("Wrong SNMP PDU digest")
        assert "Wrong SNMP PDU digest" in result
        assert "auth protocol and key" in result.lower()

    def test_unknown_error_passes_through(self):
        result = translate_error("Some random error")
        assert result == "Some random error"

    def test_includes_creds_at_info_level(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.INFO)
        try:
            creds = Credentials(
                username="thomas",
                auth_protocol=AuthProtocol.SHA256,
                auth_key="testkey123",
                priv_protocol=PrivProtocol.AES128,
                priv_key="testkey123",
                security_level=SecurityLevel.AUTH_PRIV,
            )
            result = translate_error("Wrong SNMP PDU digest", creds=creds)
            assert "thomas" in result
            assert "SHA256" in result
            assert "AES128" in result
        finally:
            logger.setLevel(logging.WARNING)

    def test_skips_creds_when_none(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.INFO)
        try:
            result = translate_error("Wrong SNMP PDU digest", creds=None)
            assert "auth protocol and key" in result.lower()
            assert "You used" not in result
        finally:
            logger.setLevel(logging.WARNING)

    def test_skips_creds_below_info(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.WARNING)
        creds = Credentials(
            username="thomas",
            auth_protocol=AuthProtocol.SHA256,
            auth_key="testkey123",
            security_level=SecurityLevel.AUTH_NO_PRIV,
        )
        result = translate_error("Wrong SNMP PDU digest", creds=creds)
        assert "thomas" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_debug.py::TestUsmReportHints tests/test_debug.py::TestTranslateError -v`
Expected: FAIL — `ImportError: cannot import name 'USM_REPORT_HINTS'`

- [ ] **Step 3: Implement `USM_REPORT_HINTS` and `translate_error()`**

Add to `src/snmpv3_utils/debug.py` (the `from __future__` and `TYPE_CHECKING` imports are already present from Task 1):

```python
USM_REPORT_HINTS: dict[str, str] = {
    "1.3.6.1.6.3.15.1.1.1.0": "Agent does not support the requested security level",
    "1.3.6.1.6.3.15.1.1.2.0": "Request outside agent's time window — possible clock skew or stale engine data",
    "1.3.6.1.6.3.15.1.1.3.0": "User not found on agent",
    "1.3.6.1.6.3.15.1.1.4.0": "Engine ID mismatch — possible stale discovery",
    "1.3.6.1.6.3.15.1.1.5.0": "Auth digest mismatch — verify auth protocol and key match agent config",
    "1.3.6.1.6.3.15.1.1.6.0": "Decryption failed — verify priv protocol and key match agent config",
}

# Map pysnmp error strings to USM report OID hints.
# pysnmp uses these exact strings in error_indication.
_ERROR_STRING_MAP: dict[str, str] = {
    "Wrong SNMP PDU digest": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.5.0"],
    "Unknown SNMP security name": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.3.0"],
    "Unsupported SNMP security level": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.1.0"],
    "Wrong SNMP PDU encoding": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.6.0"],
    "SNMP message is not in time window": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.2.0"],
    "Unknown SNMP engine ID": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.4.0"],
}


def translate_error(error_str: str, creds: Credentials | None = None) -> str:
    """Enrich a pysnmp error string with a human-readable hint.

    If the error matches a known USM report, appends an actionable hint.
    At INFO level with creds provided, also shows what credentials were used.
    Unknown errors pass through unchanged.
    """
    hint = _ERROR_STRING_MAP.get(error_str)
    if hint is None:
        return error_str

    parts = [error_str, f" — {hint}"]

    logger = logging.getLogger(_LOGGER_NAME)
    if creds is not None and logger.isEnabledFor(logging.INFO):
        cred_parts = [f"user='{creds.username}'"]
        if creds.auth_protocol:
            cred_parts.append(f"auth={creds.auth_protocol.value}")
        if creds.priv_protocol:
            cred_parts.append(f"priv={creds.priv_protocol.value}")
        parts.append(f" (You used: {', '.join(cred_parts)})")

    return "".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_debug.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run linting and type checking**

Run: `uv run ruff check src/snmpv3_utils/debug.py tests/test_debug.py && uv run mypy src/snmpv3_utils/debug.py`

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/debug.py tests/test_debug.py
git commit -m "feat(debug): add USM_REPORT_HINTS and translate_error()

Part of #36"
```

---

### Task 3: Add `-v`/`--verbose` flag to CLI

**Files:**
- Modify: `src/snmpv3_utils/cli/main.py`
- Modify: `tests/test_cli_query.py`

- [ ] **Step 1: Write failing CLI tests for verbose flags**

Append to `tests/test_cli_query.py`:

```python
class TestVerboseFlag:
    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_v_flag_accepted(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(
            app, ["-v", "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_vv_flag_accepted(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(
            app, ["-vv", "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_json_stdout_clean_with_v(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(
            app, ["-v", "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        import json
        parsed = json.loads(result.output.strip())
        assert parsed["value"] == "Linux"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_query.py::TestVerboseFlag -v`
Expected: FAIL — Typer doesn't recognize `-v` yet

- [ ] **Step 3: Add `-v`/`--verbose` to `cli/main.py` callback**

Modify `src/snmpv3_utils/cli/main.py`:

```python
# src/snmpv3_utils/cli/main.py
"""Root CLI application — registers all subcommand groups."""

from importlib.metadata import version

import typer

from snmpv3_utils.cli import auth, profile, query, trap

app = typer.Typer(
    name="snmpv3",
    help="SNMPv3 testing utility — GET, WALK, SET, traps, credential testing.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version("snmpv3-utils"))
        raise typer.Exit()


@app.callback()
def main(
    _version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (-v for info, -vv for debug).",
    ),
) -> None:
    from snmpv3_utils.debug import configure_logging

    configure_logging(verbose)


app.add_typer(
    query.app, name="query", help="SNMP query operations (get, getnext, walk, bulk, set)."
)  # noqa: E501
app.add_typer(trap.app, name="trap", help="Trap operations (send, listen).")
app.add_typer(auth.app, name="auth", help="Credential testing (check, bulk).")
app.add_typer(profile.app, name="profile", help="Manage credential profiles.")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_query.py::TestVerboseFlag -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -v`

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/cli/main.py tests/test_cli_query.py
git commit -m "feat(cli): add -v/--verbose flag to CLI callback

Part of #36"
```

---

### Task 4: Add `translate_error()` calls to CLI layer

**Files:**
- Modify: `src/snmpv3_utils/cli/query.py`
- Modify: `src/snmpv3_utils/cli/auth.py`
- Modify: `src/snmpv3_utils/cli/trap.py`
- Modify: `tests/test_cli_query.py`

- [ ] **Step 1: Write failing test for error translation in CLI**

Append to `tests/test_cli_query.py`:

```python
class TestErrorTranslation:
    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_wrong_digest_error_shows_hint(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"error": "Wrong SNMP PDU digest"}

        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code != 0
        import json
        output = json.loads(result.output.strip())
        assert "auth protocol and key" in output["error"].lower()

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_unknown_error_passes_through(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"error": "Timeout"}

        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code != 0
        import json
        output = json.loads(result.output.strip())
        assert output["error"] == "Timeout"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_query.py::TestErrorTranslation -v`
Expected: FAIL — error string is still raw "Wrong SNMP PDU digest"

- [ ] **Step 3: Add `translate_error()` to `cli/query.py`**

Add import at top of `cli/query.py`:
```python
from snmpv3_utils.debug import translate_error
```

Then update each error-handling block to translate before printing. Pattern for each command:

```python
# Before:
if "error" in result:
    print_error(result, fmt=fmt)
    raise typer.Exit(1)

# After:
if "error" in result:
    result["error"] = translate_error(result["error"], creds)
    print_error(result, fmt=fmt)
    raise typer.Exit(1)
```

Apply to: `get`, `getnext`, `walk` (use `results[0]`), `bulk` (use `results[0]`), `set_cmd`.

For `walk` and `bulk` where results is a list:
```python
if results and "error" in results[0]:
    results[0]["error"] = translate_error(results[0]["error"], creds)
    print_error(results[0], fmt=fmt)
    raise typer.Exit(1)
```

- [ ] **Step 4: Add `translate_error()` to `cli/auth.py`**

Add import:
```python
from snmpv3_utils.debug import translate_error
```

In `check` command (`creds` is already available from `build_usm_from_cli()` on line 47-58):
```python
if result["status"] == "failed":
    if "error" in result:
        result["error"] = translate_error(result["error"], creds)
    print_error(result, fmt=fmt)
    raise typer.Exit(1)
```

In `bulk` command (no `Credentials` available):
```python
# After core_bulk_check returns, translate errors in each result
for r in results:
    if "error" in r:
        r["error"] = translate_error(r["error"])
print_records(results, fmt=fmt)
```

- [ ] **Step 5: Add `translate_error()` to `cli/trap.py`**

Add import:
```python
from snmpv3_utils.debug import translate_error
```

In `send` command:
```python
if "error" in result:
    result["error"] = translate_error(result["error"], creds)
    print_error(result, fmt=fmt)
    raise typer.Exit(1)
```

In `stress` command, translate the error sample before displaying (around line 197):
```python
if samples:
    sample_msg = translate_error(samples[0], creds)
    typer.echo(
        f"Error: all {result['sent']} traps failed. Sample: {sample_msg}",
        err=True,
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_query.py::TestErrorTranslation -v`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS, no regressions

- [ ] **Step 8: Lint and type check**

Run: `uv run ruff check src/snmpv3_utils/cli/ && uv run mypy src/snmpv3_utils/cli/`

- [ ] **Step 9: Commit**

```bash
git add src/snmpv3_utils/cli/query.py src/snmpv3_utils/cli/auth.py src/snmpv3_utils/cli/trap.py tests/test_cli_query.py
git commit -m "feat(cli): translate SNMP errors to actionable hints

Part of #36"
```

---

### Task 5: Add logging calls to core modules

**Files:**
- Modify: `src/snmpv3_utils/core/query.py`
- Modify: `src/snmpv3_utils/core/auth.py`
- Modify: `src/snmpv3_utils/core/trap.py`

- [ ] **Step 1: Add logging to `core/query.py`**

Add at top of file:
```python
import logging

logger = logging.getLogger(__name__)
```

Add INFO log at the start of each async internal function (`_get`, `_getnext`, `_walk`, `_bulk`, `_set_oid`). Example for `_get`:

```python
async def _get(engine, host, oid, usm, transport):
    logger.info("GET %s OID=%s user=%s", host, oid, usm.userName)
    ...
```

Add DEBUG log for timing in the public sync wrappers. Example for `get`:

```python
def get(host, oid, usm, port=161, timeout=5, retries=3):
    import time
    start = time.monotonic()
    result = asyncio.run(_get_with_transport(host, oid, usm, port, timeout, retries))
    logger.debug("GET %s completed in %.3fs", host, time.monotonic() - start)
    return result
```

- [ ] **Step 2: Add logging to `core/auth.py`**

Add at top:
```python
import logging

logger = logging.getLogger(__name__)
```

In `check_creds`:
```python
logger.info("AUTH CHECK %s user=%s", host, username)
```

In `_bulk_check_async`:
```python
logger.info("BULK AUTH CHECK %s rows=%d", host, len(rows))
```

- [ ] **Step 3: Add logging to `core/trap.py`**

Add at top:
```python
import logging

logger = logging.getLogger(__name__)
```

In `send_trap`:
```python
logger.info("TRAP %s type=%s inform=%s user=%s", host, notification_type, inform, usm.userName)
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS — logging calls have no effect when no handler is configured

- [ ] **Step 5: Lint and type check**

Run: `uv run ruff check src/snmpv3_utils/core/ && uv run mypy src/snmpv3_utils/core/`

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/query.py src/snmpv3_utils/core/auth.py src/snmpv3_utils/core/trap.py
git commit -m "feat(core): add INFO/DEBUG logging to SNMP operations

Part of #36"
```

---

### Task 6: Final verification and cleanup

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `uv run ruff check .`

- [ ] **Step 3: Run type checking**

Run: `uv run mypy src/`

- [ ] **Step 4: Manual smoke test (if device available)**

```bash
uv run snmpv3 -v query get 192.168.15.20 1.3.6.1.2.1.1.3.0 -u thomas --auth-protocol SHA1 --auth-key snmppassword --priv-protocol AES128 --priv-key snmppassword --security-level authPriv
```

Verify: INFO-level output shows credentials used on stderr, SNMP result on stdout.

```bash
uv run snmpv3 -vv query get 192.168.15.20 1.3.6.1.2.1.1.3.0 -u thomas --auth-protocol SHA1 --auth-key wrongpassword --priv-protocol AES128 --priv-key wrongpassword --security-level authPriv
```

Verify: Error shows hint + credential context on stderr.

- [ ] **Step 5: Commit plan and spec files if not already committed**

```bash
git add docs/superpowers/specs/2026-03-22-verbose-debugging-design.md docs/superpowers/plans/2026-03-22-verbose-debugging.md
git commit -m "docs: add verbose/debug design spec and implementation plan

Part of #36"
```
