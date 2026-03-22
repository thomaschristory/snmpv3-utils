# Verbose & Debug Output for snmpv3-utils

## Problem

snmpv3-utils provides no visibility into what it sends or why requests fail. SNMP errors like "Wrong SNMP PDU digest" are raw pysnmp strings with no context — the user cannot tell whether the issue is a wrong protocol, wrong key, or agent misconfiguration without reaching for Wireshark.

## Design

### New module: `src/snmpv3_utils/debug.py`

Placed at the package root (alongside `security.py`, `output.py`, `config.py`) — not under `cli/` or `core/`. It serves the CLI layer for configuration but could also be used by library consumers.

Single owner of logging configuration, SNMP error translation, and report OID mapping. This is the only module that knows about verbosity levels and error hint logic.

**Responsibilities:**

1. **`configure_logging(verbosity: int)`** — sets up a `logging.StreamHandler` on stderr. Must be idempotent — guard against duplicate handlers on repeated calls (important for test isolation):
   - `0` (no flag) → `WARNING`
   - `1` (`-v`) → `INFO`
   - `2` (`-vv`) → `DEBUG`, plus enables pysnmp's internal debug logger (lazy import of `pysnmp.debug` inside the function body, only when `verbosity >= 2`, to keep pysnmp isolated)

   Log format:
   - INFO: `"%(levelname)s: %(message)s"`
   - DEBUG: `"%(levelname)s [%(name)s]: %(message)s"` (includes module name for tracing)

2. **`USM_REPORT_HINTS`** — module-level constant dict mapping known USM report OIDs to actionable hints. Exposed as a public constant for testing:
   - `1.3.6.1.6.3.15.1.1.1.0` (`usmStatsUnsupportedSecLevels`) → "Agent does not support the requested security level"
   - `1.3.6.1.6.3.15.1.1.2.0` (`usmStatsNotInTimeWindows`) → "Request outside agent's time window — possible clock skew or stale engine data"
   - `1.3.6.1.6.3.15.1.1.3.0` (`usmStatsUnknownUserNames`) → "User not found on agent"
   - `1.3.6.1.6.3.15.1.1.4.0` (`usmStatsUnknownEngineIDs`) → "Engine ID mismatch — possible stale discovery"
   - `1.3.6.1.6.3.15.1.1.5.0` (`usmStatsWrongDigests`) → "Auth digest mismatch — verify auth protocol and key match agent config"
   - `1.3.6.1.6.3.15.1.1.6.0` (`usmStatsDecryptionErrors`) → "Decryption failed — verify priv protocol and key match agent config"

3. **`translate_error(error_str: str, creds: Credentials | None = None) -> str`** — matches known pysnmp error strings to hints from the OID map. Returns enriched error string:
   - Always: appends the human-readable hint if the error matches a known pattern
   - At INFO level (when logger is active at that level): also appends credential context — "You used: user='thomas', auth=SHA256, priv=AES128"
   - When `creds` is `None`: skips the credential context silently (hint is still appended)
   - Unknown errors pass through unchanged

### CLI flag: `-v` / `--verbose`

Added to the top-level Typer callback in `cli/main.py`:

- Uses `count=True` so `-v` yields 1, `-vv` yields 2
- Calls `configure_logging(verbosity)` before any subcommand runs
- No changes to individual subcommand signatures
- Note: `-v` (lowercase) coexists with the existing `-V` (uppercase) for `--version`. Typer handles case-sensitivity correctly; both will appear distinctly in `--help` output.

### Logging in core modules

Core modules (`core/query.py`, `core/auth.py`, `core/trap.py`) add `logging.getLogger(__name__)` calls:

- **INFO level:** log before each SNMP operation — username, auth protocol, priv protocol, host, port, OID
- **DEBUG level:** timing, engine discovery details

Core modules use only stdlib `logging` — they never import from `debug.py`. The logger is configured by the CLI layer via `debug.py`, preserving the architecture rule that core has no CLI dependencies.

### Enhanced error output

The **CLI layer** calls `translate_error()` on error strings before passing them to `print_error()`.

**Integration with dict-based error flow:** CLI commands extract the error string from the result dict, translate it, and put it back before printing:

```python
if "error" in result:
    result["error"] = translate_error(result["error"], creds)
    print_error(result, fmt=fmt)
    raise typer.Exit(1)
```

**Command-specific handling:**

- `cli/query.py` and `cli/auth.py:check` — `Credentials` object is available from `build_usm_from_cli()`, passed to `translate_error()`.
- `cli/auth.py:bulk` — processes multiple credential rows from CSV. No single `Credentials` object. `translate_error()` is called with `creds=None` for each error result (hint is still shown, credential context is skipped). This is acceptable since the bulk output already includes the username per row.
- `cli/trap.py` — same pattern as query commands where `Credentials` is available.

**Design choices:**
- Core modules continue to return raw error dicts unchanged
- `output.py` stays unchanged — it prints whatever error string it receives
- Error translation lives entirely in the CLI layer

### pysnmp debug at `-vv`

At verbosity level 2, `configure_logging()` enables pysnmp's internal debug logger. The `pysnmp.debug` import is lazy (inside the function body) to keep pysnmp isolated from `debug.py` at import time. This is a deliberate narrow exception to the "only `security.py` imports pysnmp" rule — `pysnmp.debug` is a diagnostic utility, not an auth/priv constant.

## Output destination

All verbose/debug output goes to **stderr** via `logging.StreamHandler(sys.stderr)`. SNMP results on stdout remain clean — `snmpv3 query get ... -f json | jq` works regardless of verbosity level.

## Testing

- **`test_debug.py`:**
  - `configure_logging()` sets correct levels and is idempotent (no duplicate handlers)
  - `translate_error()` maps known errors to hints
  - `translate_error()` includes credential context at INFO level, skips it when `creds=None`
  - Unknown errors pass through unchanged
  - `USM_REPORT_HINTS` contains all expected OIDs
  - At verbosity 2, mock `pysnmp.debug.setLogger` to verify it was called
- **CLI tests:** `-v` and `-vv` flags accepted, debug output goes to stderr not stdout, JSON output on stdout remains clean with `-v` active
- **No changes to existing core tests** — core returns the same raw error dicts as today

## Architecture compliance

- `debug.py` — top-level package module. Imports `logging` and `Credentials` from `security.py`. Lazy-imports `pysnmp.debug` only at `-vv`.
- `core/` — only imports `logging` (stdlib). No imports from `debug.py`, no CLI dependencies.
- `cli/` — imports `translate_error` and `configure_logging` from `debug.py`. Calls `translate_error()` before `print_error()`.
- `output.py` — unchanged.
