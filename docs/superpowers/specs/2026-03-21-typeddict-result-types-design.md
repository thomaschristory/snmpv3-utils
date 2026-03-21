# TypedDict Result Types for SNMP Operations

**Issue:** #7
**Date:** 2026-03-21
**Status:** Approved

## Problem

All core/ functions return `dict[str, Any]` or `list[dict[str, Any]]`. Consumers have no static guarantees about which keys exist. This makes it easy to mistype a key or forget to handle an error shape.

## Design

### Approach: Union of Success/Error TypedDicts

Each operation gets a pair of TypedDicts (success and error) combined into a Union alias. Where a `status` key already exists on both sides of the union, use `Literal` types as a discriminant for mypy narrowing.

### New File: `src/snmpv3_utils/types.py`

```python
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
    type: str          # "trap" or "inform"
    inform: bool

class TrapError(TypedDict):
    error: str
    host: str
    type: str          # "trap" or "inform"
    inform: bool

TrapResult = Union[TrapSuccess, TrapError]
```

### mypy Narrowing

**With `Literal` discriminant (AuthResult):** mypy can narrow directly on `result["status"]`:
```python
result = check_creds(host, usm, username=name)
if result["status"] == "failed":
    # mypy knows: AuthError
else:
    # mypy knows: AuthSuccess
```

**Without shared discriminant (VarBindResult, SetResult, TrapResult):** mypy cannot narrow `Union[TypedDict, TypedDict]` via `"error" in result`. Consumers should use `result.get("error")` or a runtime check. For strict typing, a helper or `cast()` is needed. This is a known mypy limitation — the types still provide documentation value and catch key typos, even without automatic narrowing.

### Changes Per Module

#### `core/query.py`
- Import result types from `types.py`
- `_var_bind_to_dict` returns `VarBindSuccess`
- `get` returns `VarBindResult`
- `getnext` returns `VarBindResult`
- `walk` returns `list[VarBindResult]`
- `bulk` returns `list[VarBindResult]`
- `set_oid` returns `SetResult`
- **Bug fix:** `set_oid`'s invalid-value-type error path currently returns `{"error": "..."}` without `host` or `oid`. Fix to include both keys for consistency with `SetError`.

#### `core/auth.py`
- Import result types from `types.py`
- `check_creds` returns `AuthResult`
- `bulk_check` returns `list[AuthResult]`
- **Bug fix:** `check_creds` uses `result.get("value")` for `sysdescr`, which can return `None`. Change to `result["value"]` since we've already confirmed `"error" not in result` at that point (the key is guaranteed present in `VarBindSuccess`).

#### `core/trap.py`
- Import result types from `types.py`
- `send_trap` returns `TrapResult`

#### `__init__.py`
- Re-export all public types: `VarBindSuccess`, `VarBindError`, `VarBindResult`, `SetSuccess`, `SetError`, `SetResult`, `AuthSuccess`, `AuthError`, `AuthResult`, `TrapSuccess`, `TrapError`, `TrapResult`

#### `output.py`
- No changes. It consumes dicts generically (iterates keys, reads `record.get("error")`). Annotation changes are not needed and would over-constrain it.

### Out of Scope

- **`trap.py:listen()`** — currently a stub raising `NotImplementedError`. A `TrapReceiveResult` TypedDict will be defined when #1 is implemented.

### Design Notes

- **`VarBindSuccess` has no `host` key** while all error types and other success types include `host`. This matches current behavior: query success results come from pysnmp's var-bind pairs which contain only OID+value. The caller already knows the host. Changing this would alter runtime behavior for the most-used operations.
- **`set_oid` consistency fix** is the only runtime behavior change in this spec.
- **`check_creds` `.get()` → `[]` fix** is safe because the code path is only reached when `get()` returned a `VarBindSuccess`, which guarantees the `value` key exists.

### Testing Strategy
- Existing 56 tests continue to pass (no runtime changes beyond the two minor fixes)
- Add key-presence assertions to existing tests to validate dict shapes match the TypedDicts
- mypy validates all return annotations match actual dict literals
