# TypedDict Result Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace all `dict[str, Any]` return types in core/ with typed `Union[SuccessType, ErrorType]` TypedDicts.

**Architecture:** New `types.py` module defines all TypedDicts. Core modules import and use them as return annotations. `__init__.py` re-exports for public API. Two minor bug fixes in `query.py` and `auth.py`.

**Tech Stack:** Python `typing.TypedDict`, `typing.Literal`, `typing.Union`. Tools: mypy, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-03-21-typeddict-result-types-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/snmpv3_utils/types.py` | All TypedDict definitions and Union aliases |
| Modify | `src/snmpv3_utils/core/query.py` | Import types, update return annotations |
| Modify | `src/snmpv3_utils/core/auth.py` | Import types, update return annotations, fix `.get()` |
| Modify | `src/snmpv3_utils/core/trap.py` | Import types, update return annotations |
| Modify | `src/snmpv3_utils/__init__.py` | Append re-exports for all public types |
| Modify | `tests/test_query.py` | Add key-shape assertions |
| Modify | `tests/test_auth.py` | Add key-shape assertions, fix mock return values |
| Modify | `tests/test_trap.py` | Add key-shape assertions |

---

### Task 1: Create `types.py` with all TypedDict definitions

**Files:**
- Create: `src/snmpv3_utils/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write the test file**

```python
"""Tests that TypedDict types are importable and have expected keys."""

from snmpv3_utils.types import (
    AuthError,
    AuthResult,
    AuthSuccess,
    SetError,
    SetResult,
    SetSuccess,
    TrapError,
    TrapResult,
    TrapSuccess,
    VarBindError,
    VarBindResult,
    VarBindSuccess,
)


def test_varbind_success_keys() -> None:
    record: VarBindSuccess = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
    assert set(record.keys()) == {"oid", "value"}


def test_varbind_error_keys() -> None:
    record: VarBindError = {"error": "timeout", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"}
    assert set(record.keys()) == {"error", "host", "oid"}


def test_set_success_keys() -> None:
    record: SetSuccess = {"status": "ok", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0", "value": "42"}
    assert set(record.keys()) == {"status", "host", "oid", "value"}


def test_set_error_keys() -> None:
    record: SetError = {"error": "timeout", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"}
    assert set(record.keys()) == {"error", "host", "oid"}


def test_auth_success_keys() -> None:
    record: AuthSuccess = {"status": "ok", "host": "192.168.1.1", "username": "admin", "sysdescr": "Linux"}
    assert set(record.keys()) == {"status", "host", "username", "sysdescr"}


def test_auth_error_keys() -> None:
    record: AuthError = {"status": "failed", "host": "192.168.1.1", "username": "admin", "error": "timeout"}
    assert set(record.keys()) == {"status", "host", "username", "error"}


def test_trap_success_keys() -> None:
    record: TrapSuccess = {"status": "ok", "host": "192.168.1.1", "type": "trap", "inform": False}
    assert set(record.keys()) == {"status", "host", "type", "inform"}


def test_trap_error_keys() -> None:
    record: TrapError = {"error": "timeout", "host": "192.168.1.1", "type": "trap", "inform": False}
    assert set(record.keys()) == {"error", "host", "type", "inform"}


def test_union_aliases_exist() -> None:
    """Verify union aliases are importable (type-level only)."""
    assert VarBindResult is not None
    assert SetResult is not None
    assert AuthResult is not None
    assert TrapResult is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'snmpv3_utils.types'`

- [ ] **Step 3: Create `types.py`**

```python
"""Typed result dictionaries for SNMP operations."""

from typing import Literal, TypedDict, Union

# --- Query operations (get, getnext, walk, bulk) ---


class VarBindSuccess(TypedDict):
    oid: str
    value: str


class VarBindError(TypedDict):
    error: str
    host: str
    oid: str


VarBindResult = Union[VarBindSuccess, VarBindError]

# --- Set operation ---


class SetSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    oid: str
    value: str


class SetError(TypedDict):
    error: str
    host: str
    oid: str


SetResult = Union[SetSuccess, SetError]

# --- Auth operations (check_creds, bulk_check) ---


class AuthSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    username: str
    sysdescr: str


class AuthError(TypedDict):
    status: Literal["failed"]
    host: str
    username: str
    error: str


AuthResult = Union[AuthSuccess, AuthError]

# --- Trap operation ---


class TrapSuccess(TypedDict):
    status: Literal["ok"]
    host: str
    type: str
    inform: bool


class TrapError(TypedDict):
    error: str
    host: str
    type: str
    inform: bool


TrapResult = Union[TrapSuccess, TrapError]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_types.py -v`
Expected: 9 passed

- [ ] **Step 5: Run mypy and ruff**

Run: `uv run mypy src/snmpv3_utils/types.py && uv run ruff check src/snmpv3_utils/types.py && uv run ruff format --check src/snmpv3_utils/types.py`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/types.py tests/test_types.py
git commit -m "feat(types): add TypedDict result types for all SNMP operations (#7)"
```

---

### Task 2: Annotate `core/query.py` and fix `set_oid` bug

**Files:**
- Modify: `src/snmpv3_utils/core/query.py` — imports (add to local-imports group after pysnmp block), return annotations, `set_oid` bug fix
- Modify: `tests/test_query.py` — add key assertions

- [ ] **Step 1: Add key-shape assertions to existing tests**

In `tests/test_query.py`, add assertions to verify dict shapes match TypedDicts. Add these assertions to the existing test methods:

In `test_returns_dict_with_oid_and_value` (line 27) — add after existing assert:
```python
assert set(result.keys()) == {"oid", "value"}
```

In `test_returns_error_dict_on_failure` (line 34) — add after existing assert:
```python
assert set(result.keys()) == {"error", "host", "oid"}
```

In `test_returns_dict_with_next_oid` (line 43) — add:
```python
assert set(result.keys()) == {"oid", "value"}
```

In `TestWalk.test_returns_list_of_dicts` (line 52) — add after existing assert:
```python
assert all(set(r.keys()) == {"oid", "value"} for r in result)
```

In `TestBulk.test_returns_list_of_dicts` (line 71) — add after existing assert:
```python
assert all(set(r.keys()) == {"oid", "value"} for r in result)
```

In `TestBulk.test_returns_error_on_failure` (line 80) — add:
```python
assert set(result[0].keys()) == {"error", "host", "oid"}
```

In `TestSet.test_returns_success_dict` (line 90) — add:
```python
assert set(result.keys()) == {"status", "host", "oid", "value"}
```

In `TestSet.test_returns_error_on_failure` (line 95) — add:
```python
assert set(result.keys()) == {"error", "host", "oid"}
```

Also add a new test for the `set_oid` invalid-type error path (no `@patch` needed — early return before `setCmd` is called):
```python
def test_set_returns_error_with_host_on_invalid_type(self, usm):
    result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.1.0", "val", "bogus", usm)
    assert "error" in result
    assert set(result.keys()) == {"error", "host", "oid"}
```

- [ ] **Step 2: Run tests — new assertion for invalid-type error should fail**

Run: `uv run pytest tests/test_query.py -v`
Expected: `test_set_returns_error_with_host_on_invalid_type` FAILS (missing `host` and `oid` keys)

- [ ] **Step 3: Update `core/query.py` imports and annotations**

At top of `query.py`, add to local-imports group (after the pysnmp import block, around line 35):
```python
from snmpv3_utils.types import SetResult, VarBindResult, VarBindSuccess
```

Update function signatures:
- `_var_bind_to_dict` (line 146): return `VarBindSuccess`
- `get` (line 155): return `VarBindResult`
- `getnext` (line 180): return `VarBindResult`
- `walk` (line 205): return `list[VarBindResult]`
- `bulk` (line 238): return `list[VarBindResult]`
- `set_oid` (line 274): return `SetResult`

Remove unused `Any` import from `from typing import Any` (line 9) if no longer needed.

Fix `set_oid` invalid-type error (line 286) — change:
```python
return {"error": f"Unknown type '{value_type}'. Use int, str, or hex."}
```
to:
```python
return {"error": f"Unknown type '{value_type}'. Use int, str, or hex.", "host": host, "oid": oid}
```

Fix `set_oid` invalid-value error (line 296) — verify it already has `host` and `oid`. If not, add them.

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/test_query.py -v`
Expected: all pass

- [ ] **Step 5: Run mypy and ruff**

Run: `uv run mypy src/snmpv3_utils/core/query.py && uv run ruff check src/snmpv3_utils/core/query.py && uv run ruff format --check src/snmpv3_utils/core/query.py`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "feat(query): annotate return types with TypedDicts, fix set_oid error consistency (#7)"
```

---

### Task 3: Annotate `core/auth.py` and fix `.get()` bug

**Files:**
- Modify: `src/snmpv3_utils/core/auth.py` — imports (add to local-imports group after line 21), return annotations, `.get()` fix
- Modify: `tests/test_auth.py` — add key assertions, fix mock return values

- [ ] **Step 1: Add key-shape assertions and fix mock return values**

In `tests/test_auth.py`:

In `test_success_when_get_returns_value` (line 18) — add:
```python
assert set(result.keys()) == {"status", "host", "username", "sysdescr"}
assert isinstance(result["sysdescr"], str)
```

In `test_failure_when_get_returns_error` (line 24) — add:
```python
assert set(result.keys()) == {"status", "host", "username", "error"}
```

In `test_bulk_returns_result_per_row` (line 51) — the existing mock `side_effect` returns dicts without `sysdescr`/`error` keys. Fix the mock return values to match the real `check_creds` output shape, then add the assertion:

Update the mock `side_effect` to return full-shaped dicts (with `sysdescr` for success, `error` for failure), then add:
```python
assert all(set(r.keys()) in ({"status", "host", "username", "sysdescr"}, {"status", "host", "username", "error"}) for r in results)
```

- [ ] **Step 2: Run tests — `isinstance(result["sysdescr"], str)` should pass now but will serve as a regression guard**

Run: `uv run pytest tests/test_auth.py -v`
Expected: all pass (assertions match current behavior after mock fix)

- [ ] **Step 3: Update `core/auth.py` imports and annotations**

Add import (in the local-imports group, after the existing `snmpv3_utils` imports around line 21):
```python
from snmpv3_utils.types import AuthResult
```

Update function signatures:
- `check_creds` (line 26): return `AuthResult`
- `bulk_check` (line 44): return `list[AuthResult]`

Fix line 41 — change:
```python
return {"status": "ok", "host": host, "username": username, "sysdescr": result.get("value")}
```
to:
```python
return {"status": "ok", "host": host, "username": username, "sysdescr": result["value"]}
```

Remove unused `Any` import if no longer needed.

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: all pass

- [ ] **Step 5: Run mypy and ruff**

Run: `uv run mypy src/snmpv3_utils/core/auth.py && uv run ruff check src/snmpv3_utils/core/auth.py && uv run ruff format --check src/snmpv3_utils/core/auth.py`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/auth.py tests/test_auth.py
git commit -m "feat(auth): annotate return types with TypedDicts, fix sysdescr .get() (#7)"
```

---

### Task 4: Annotate `core/trap.py`

**Files:**
- Modify: `src/snmpv3_utils/core/trap.py` — imports (add to local-imports group after pysnmp block), return annotations
- Modify: `tests/test_trap.py` — add key assertions

- [ ] **Step 1: Add key-shape assertions to existing tests**

In `tests/test_trap.py`:

In `test_send_trap_returns_ok` (line 16) — add:
```python
assert set(result.keys()) == {"status", "host", "type", "inform"}
```

In `test_send_inform_returns_ok` (line 22) — add:
```python
assert set(result.keys()) == {"status", "host", "type", "inform"}
```

In `test_send_trap_returns_error_on_failure` (line 29) — add:
```python
assert set(result.keys()) == {"error", "host", "type", "inform"}
```

In `test_send_trap_returns_error_on_no_response` (line 35) — add:
```python
assert set(result.keys()) == {"error", "host", "type", "inform"}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_trap.py -v`
Expected: all pass

- [ ] **Step 3: Update `core/trap.py` imports and annotations**

Add import (in the local-imports group, after the pysnmp import block around line 26):
```python
from snmpv3_utils.types import TrapResult
```

Update function signature:
- `send_trap` (line 71): return `TrapResult`

Remove unused `Any` import if no longer needed.

- [ ] **Step 4: Run tests to verify all pass**

Run: `uv run pytest tests/test_trap.py -v`
Expected: all pass

- [ ] **Step 5: Run mypy and ruff**

Run: `uv run mypy src/snmpv3_utils/core/trap.py && uv run ruff check src/snmpv3_utils/core/trap.py && uv run ruff format --check src/snmpv3_utils/core/trap.py`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/trap.py tests/test_trap.py
git commit -m "feat(trap): annotate send_trap return type with TypedDicts (#7)"
```

---

### Task 5: Re-export types from `__init__.py` and final verification

**Files:**
- Modify: `src/snmpv3_utils/__init__.py` — append re-exports (file is currently empty)
- Modify: `tests/test_types.py` — add test for package-root imports

- [ ] **Step 1: Add test for package-root re-exports**

Add to `tests/test_types.py`:
```python
def test_types_importable_from_package_root() -> None:
    """Verify all types are re-exported from snmpv3_utils."""
    from snmpv3_utils import (
        AuthError,
        AuthResult,
        AuthSuccess,
        SetError,
        SetResult,
        SetSuccess,
        TrapError,
        TrapResult,
        TrapSuccess,
        VarBindError,
        VarBindResult,
        VarBindSuccess,
    )
    assert VarBindSuccess is not None
    assert VarBindError is not None
    assert VarBindResult is not None
    assert SetSuccess is not None
    assert SetError is not None
    assert SetResult is not None
    assert AuthSuccess is not None
    assert AuthError is not None
    assert AuthResult is not None
    assert TrapSuccess is not None
    assert TrapError is not None
    assert TrapResult is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_types.py::test_types_importable_from_package_root -v`
Expected: FAIL — `ImportError: cannot import name 'AuthError' from 'snmpv3_utils'`

- [ ] **Step 3: Append re-exports to `__init__.py`**

Append to `src/snmpv3_utils/__init__.py` (do not overwrite existing content):
```python
from snmpv3_utils.types import (
    AuthError,
    AuthResult,
    AuthSuccess,
    SetError,
    SetResult,
    SetSuccess,
    TrapError,
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
    "TrapResult",
    "TrapSuccess",
    "VarBindError",
    "VarBindResult",
    "VarBindSuccess",
]
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests pass (56 existing + 10 new type tests = 66+)

- [ ] **Step 5: Run full lint and type check**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/`
Expected: all clean

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/__init__.py tests/test_types.py
git commit -m "feat: re-export TypedDict result types from package root (#7)"
```
