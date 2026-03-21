# TypedDict Result Types for SNMP Operations

**Issue:** #7
**Date:** 2026-03-21
**Status:** Approved

## Problem

All core/ functions return `dict[str, Any]` or `list[dict[str, Any]]`. Consumers have no static guarantees about which keys exist. This makes it easy to mistype a key or forget to handle an error shape.

## Design

### Approach: Union of Success/Error TypedDicts

Each operation gets a pair of TypedDicts (success and error) combined into a Union alias. This gives strong static guarantees — after checking for `"error"` in a result, the type narrowing tells you exactly which keys are available.

### New File: `src/snmpv3_utils/types.py`

```python
from typing import TypedDict, Union

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
    status: str        # "ok"
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
    status: str        # "ok"
    host: str
    username: str
    sysdescr: str

class AuthError(TypedDict):
    status: str        # "failed"
    host: str
    username: str
    error: str

AuthResult = Union[AuthSuccess, AuthError]

# --- Trap operation ---

class TrapSuccess(TypedDict):
    status: str        # "ok"
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

### Changes Per Module

#### `core/query.py`
- Import result types from `types.py`
- `_var_bind_to_dict` returns `VarBindSuccess`
- `get` returns `VarBindResult`
- `getnext` returns `VarBindResult`
- `walk` returns `list[VarBindResult]`
- `bulk` returns `list[VarBindResult]`
- `set_oid` returns `SetResult`
- **Bug fix:** `set_oid`'s invalid-value-type error path currently returns `{"error": "..."}` without `host` or `oid`. Fix to include both keys for consistency with all other error dicts.

#### `core/auth.py`
- Import result types from `types.py`
- `check_creds` returns `AuthResult`
- `bulk_check` returns `list[AuthResult]`

#### `core/trap.py`
- Import result types from `types.py`
- `send_trap` returns `TrapResult`

#### `__init__.py`
- Re-export all public types: `VarBindSuccess`, `VarBindError`, `VarBindResult`, `SetSuccess`, `SetError`, `SetResult`, `AuthSuccess`, `AuthError`, `AuthResult`, `TrapSuccess`, `TrapError`, `TrapResult`

#### `output.py`
- No changes. It consumes dicts generically (iterates keys, reads `record.get("error")`). Annotation changes are not needed and would over-constrain it.

### What Does NOT Change
- No runtime behavior changes (TypedDicts are structural, not enforced at runtime)
- No changes to CLI layer
- No changes to output formatting
- Only behavioral fix: `set_oid` invalid-type error path adds `host` and `oid`

### Testing Strategy
- Existing 56 tests continue to pass (no runtime changes)
- Add key-presence assertions to existing tests to validate dict shapes match the TypedDicts
- mypy validates all return annotations match actual dict literals

### Type Narrowing Pattern for Consumers
```python
result = get(host, oid, usm)
if "error" in result:
    # result is VarBindError — has error, host, oid
    print(result["error"])
else:
    # result is VarBindSuccess — has oid, value
    print(result["value"])
```
