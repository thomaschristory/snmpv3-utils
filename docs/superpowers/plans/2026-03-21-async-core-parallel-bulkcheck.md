# Async Core + Parallel bulk_check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract async internals from `core/query.py` and parallelize `bulk_check` in `core/auth.py` using `asyncio.gather()`, while keeping the public sync API unchanged.

**Architecture:** Two-level async split — private `_get`/`_getnext`/etc. accept engine+transport for reuse from other async contexts, while `_get_with_transport`/etc. are self-contained async wrappers that create engine+transport in a single event loop. Public sync functions call `asyncio.run()` once on the `_*_with_transport` variant. `bulk_check` creates one engine + transport and fans out via `asyncio.gather()`.

**Tech Stack:** Python 3.11+, pysnmp 7 (lextudio), asyncio, pytest, AsyncMock

**Spec:** `docs/superpowers/specs/2026-03-21-async-core-parallel-bulkcheck-design.md`

**Important mock note:** Every test that calls a public sync function (`get`, `getnext`, etc.) must patch BOTH the pysnmp async command (`_get_cmd_async` etc.) AND `UdpTransportTarget.create`, since `_*_with_transport` calls `await UdpTransportTarget.create(...)` which would open a real UDP socket.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/snmpv3_utils/core/query.py` | Async internals (`_get`, `_getnext`, `_walk`, `_bulk`, `_set_oid`) + `_*_with_transport` wrappers + unchanged public sync API |
| `src/snmpv3_utils/core/auth.py` | `_check_creds_async`, `_parse_row_to_usm`, `_bulk_check_async` + extended `bulk_check` with `max_concurrent` param |
| `tests/test_query.py` | Updated mocks: `AsyncMock` on pysnmp async functions + `UdpTransportTarget.create` |
| `tests/test_auth.py` | Updated existing bulk_check tests + new concurrency tests |

---

## Task 1: Refactor query.py — Extract `_get` and `_get_with_transport`

**Files:**
- Modify: `src/snmpv3_utils/core/query.py:45-55` (remove `getCmd`), `:157-179` (rewrite `get`)
- Modify: `tests/test_query.py:1-41`

Start with `get` since it's the simplest operation and establishes the pattern. Do NOT remove `_transport` helper yet — `getnext`, `walk`, `bulk`, `set_oid` still use it.

- [ ] **Step 1: Update test_query.py TestGet to use AsyncMock**

Replace the mock target from the sync wrapper `getCmd` to the pysnmp async function `_get_cmd_async`. Use `AsyncMock` since the target is now an async coroutine. Also patch `UdpTransportTarget.create` to prevent real socket creation.

```python
# tests/test_query.py — replace imports
from unittest.mock import AsyncMock, MagicMock, patch
```

```python
# TestGet — replace both test methods
class TestGet:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._get_cmd_async", new_callable=AsyncMock)
    def test_returns_dict_with_oid_and_value(self, mock_get, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_get.return_value = _mock_cmd_result()[0]
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert "value" in result
        assert set(result.keys()) == {"oid", "value"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._get_cmd_async", new_callable=AsyncMock)
    def test_returns_error_dict_on_failure(self, mock_get, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_get.return_value = ("Timeout", None, None, [])
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}
```

Note: `_mock_cmd_result()` returns `[(None, None, None, [var_bind])]` — a list. The async function returns a single tuple, not a list, so we use `[0]` to unwrap. Decorators are applied bottom-up, so `mock_get` is the first arg, `mock_transport` second.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_query.py::TestGet -v`
Expected: FAIL — mock target `_get_cmd_async` not yet called by the new async flow.

- [ ] **Step 3: Implement `_get` and `_get_with_transport` in query.py**

Remove ONLY the `getCmd` sync wrapper (lines 45-55). Keep `_transport`, `nextCmd`, `setCmd`, `walkCmd`, `bulkCmd` intact. Add after the remaining sync wrappers section:

```python
# ---------------------------------------------------------------------------
# Async internals — reusable from other async contexts (e.g. bulk_check).
# The _*_cmd_async aliases above are the mock targets in tests.
# ---------------------------------------------------------------------------


async def _get(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> VarBindResult:
    """Async GET: fetch a single OID value."""
    try:
        error_indication, error_status, _, var_binds = await _get_cmd_async(
            engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return _var_bind_to_dict(var_binds[0])


async def _get_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> VarBindResult:
    """Self-contained async GET: creates engine + transport in one event loop."""
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _get(engine, host, oid, usm, transport)
```

Update the public `get()` function:

```python
def get(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> VarBindResult:
    """Fetch a single OID value."""
    return asyncio.run(_get_with_transport(host, oid, usm, port, timeout, retries))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_query.py::TestGet -v`
Expected: PASS

- [ ] **Step 5: Run full query test suite to confirm no regressions**

Run: `uv run pytest tests/test_query.py -v`
Expected: All PASS (other tests still use old sync wrappers which still exist)

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "refactor(query): extract async _get and _get_with_transport (#5)"
```

---

## Task 2: Refactor query.py — Extract `_getnext` and `_getnext_with_transport`

**Files:**
- Modify: `src/snmpv3_utils/core/query.py` (remove `nextCmd`, add async functions, rewrite `getnext`)
- Modify: `tests/test_query.py:43-51`

Same pattern as Task 1, for `getnext`.

- [ ] **Step 1: Update TestGetnext to use AsyncMock**

```python
class TestGetnext:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._next_cmd_async", new_callable=AsyncMock)
    def test_returns_dict_with_next_oid(self, mock_next, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_next.return_value = _mock_cmd_result(oid="1.3.6.1.2.1.1.2.0")[0]
        result = getnext("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert set(result.keys()) == {"oid", "value"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_query.py::TestGetnext -v`
Expected: FAIL

- [ ] **Step 3: Implement `_getnext` and `_getnext_with_transport`**

Remove the `nextCmd` sync wrapper. Add:

```python
async def _getnext(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> VarBindResult:
    """Async GETNEXT: return the next OID after the given one."""
    try:
        error_indication, error_status, _, var_binds = await _next_cmd_async(
            engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return _var_bind_to_dict(var_binds[0])


async def _getnext_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> VarBindResult:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _getnext(engine, host, oid, usm, transport)
```

Update public `getnext()`:

```python
def getnext(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> VarBindResult:
    """Return the next OID after the given one (single GETNEXT step)."""
    return asyncio.run(_getnext_with_transport(host, oid, usm, port, timeout, retries))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_query.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "refactor(query): extract async _getnext and _getnext_with_transport (#5)"
```

---

## Task 3: Refactor query.py — Extract `_walk` and `_walk_with_transport`

**Files:**
- Modify: `src/snmpv3_utils/core/query.py` (remove `walkCmd`, add async functions, rewrite `walk`)
- Modify: `tests/test_query.py:53-70`

Walk is different — `_walk_cmd_async` is an async generator, not a coroutine. The mock needs special handling (async generator, not `AsyncMock.return_value`).

- [ ] **Step 1: Update TestWalk to use async generator mock**

```python
class TestWalk:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._walk_cmd_async")
    def test_returns_list_of_dicts(self, mock_walk, mock_transport, usm):
        mock_transport.return_value = MagicMock()

        async def _async_gen(*args, **kwargs):
            yield (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.1.0", "Linux")[0][3])
            yield (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.2.0", "sysObjectID")[0][3])

        mock_walk.return_value = _async_gen()
        results = walk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._walk_cmd_async")
    def test_empty_walk_returns_empty_list(self, mock_walk, mock_transport, usm):
        mock_transport.return_value = MagicMock()

        async def _async_gen(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_walk.return_value = _async_gen()
        results = walk("192.168.1.1", "1.3.6.1.2.1.99", usm)
        assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_query.py::TestWalk -v`
Expected: FAIL

- [ ] **Step 3: Implement `_walk` and `_walk_with_transport`**

Remove the `walkCmd` sync wrapper. Add:

```python
async def _walk(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> list[VarBindResult]:
    """Async WALK: traverse subtree via repeated GETNEXT."""
    results: list[VarBindResult] = []
    async for error_indication, error_status, _, var_binds in _walk_cmd_async(
        engine,
        usm,
        transport,
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append(
                {"error": str(error_indication or error_status), "host": host, "oid": oid}
            )
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


async def _walk_with_transport(
    host: str, oid: str, usm: UsmUserData, port: int, timeout: int, retries: int
) -> list[VarBindResult]:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    return await _walk(engine, host, oid, usm, transport)
```

Update public `walk()`:

```python
def walk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> list[VarBindResult]:
    """Traverse the subtree rooted at oid via repeated GETNEXT."""
    return asyncio.run(_walk_with_transport(host, oid, usm, port, timeout, retries))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_query.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "refactor(query): extract async _walk and _walk_with_transport (#5)"
```

---

## Task 4: Refactor query.py — Extract `_bulk` and `_bulk_with_transport`

**Files:**
- Modify: `src/snmpv3_utils/core/query.py` (remove `bulkCmd`, add async functions, rewrite `bulk`)
- Modify: `tests/test_query.py:73-91`

`bulk_cmd` is a coroutine (not async generator), similar to `get`/`getnext` but with `non_repeaters` and `max_repetitions` params and returns a list.

- [ ] **Step 1: Update TestBulk to use AsyncMock**

```python
class TestBulk:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._bulk_cmd_async", new_callable=AsyncMock)
    def test_returns_list_of_dicts(self, mock_bulk, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_bulk.return_value = _mock_cmd_result()[0]
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._bulk_cmd_async", new_callable=AsyncMock)
    def test_returns_error_on_failure(self, mock_bulk, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_bulk.return_value = ("Timeout", None, None, [])
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert len(results) == 1
        assert "error" in results[0]
        assert set(results[0].keys()) == {"error", "host", "oid"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_query.py::TestBulk -v`
Expected: FAIL

- [ ] **Step 3: Implement `_bulk` and `_bulk_with_transport`**

Remove the `bulkCmd` sync wrapper. Add:

```python
async def _bulk(
    engine: SnmpEngine,
    host: str,
    oid: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    """Async GETBULK retrieval."""
    try:
        error_indication, error_status, _, var_binds = await _bulk_cmd_async(
            engine,
            usm,
            transport,
            ContextData(),
            0,
            max_repetitions,
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        )
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    results: list[VarBindResult] = []
    if error_indication or error_status:
        results.append(
            {"error": str(error_indication or error_status), "host": host, "oid": oid}
        )
    else:
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


async def _bulk_with_transport(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int,
    timeout: int,
    retries: int,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        return [{"error": str(exc), "host": host, "oid": oid}]
    return await _bulk(engine, host, oid, usm, transport, max_repetitions)
```

Update public `bulk()`:

```python
def bulk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
    max_repetitions: int = 25,
) -> list[VarBindResult]:
    """GETBULK retrieval."""
    return asyncio.run(
        _bulk_with_transport(host, oid, usm, port, timeout, retries, max_repetitions)
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_query.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "refactor(query): extract async _bulk and _bulk_with_transport (#5)"
```

---

## Task 5: Refactor query.py — Extract `_set_oid`, remove `_transport`, final cleanup

**Files:**
- Modify: `src/snmpv3_utils/core/query.py` (remove `setCmd`, `_transport`, add async functions, rewrite `set_oid`)
- Modify: `tests/test_query.py:94-113`

`set_oid` has extra pre-validation (value_type check, value conversion) that stays in the sync function. Only the SNMP call moves to async. Also remove `_transport` helper — all callers are now async.

- [ ] **Step 1: Update TestSet to use AsyncMock**

```python
class TestSet:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._set_cmd_async", new_callable=AsyncMock)
    def test_returns_success_dict(self, mock_set, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_set.return_value = (None, None, None, [])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "myrouter", "str", usm)
        assert result.get("status") == "ok"
        assert set(result.keys()) == {"status", "host", "oid", "value"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._set_cmd_async", new_callable=AsyncMock)
    def test_returns_error_on_failure(self, mock_set, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_set.return_value = ("noSuchObject", None, None, [])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "x", "str", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}

    def test_set_returns_error_with_host_on_invalid_type(self, usm):
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.1.0", "val", "bogus", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_query.py::TestSet -v`
Expected: FAIL

- [ ] **Step 3: Implement `_set_oid` and `_set_oid_with_transport`**

Remove the `setCmd` sync wrapper. Add:

```python
async def _set_oid(
    engine: SnmpEngine,
    host: str,
    oid: str,
    snmp_value: Any,
    value: str,
    usm: UsmUserData,
    transport: UdpTransportTarget,
) -> SetResult:
    """Async SET: set an OID to a value."""
    try:
        error_indication, error_status, _, _ = await _set_cmd_async(
            engine,
            usm,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid), snmp_value),
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return {"status": "ok", "host": host, "oid": oid, "value": value}


async def _set_oid_with_transport(
    host: str,
    oid: str,
    snmp_value: Any,
    value: str,
    usm: UsmUserData,
    port: int,
    timeout: int,
    retries: int,
) -> SetResult:
    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        return {"error": str(exc), "host": host, "oid": oid}
    return await _set_oid(engine, host, oid, snmp_value, value, usm, transport)
```

Update public `set_oid()` — value_type validation + value conversion stays sync, only SNMP call is async:

```python
def set_oid(
    host: str,
    oid: str,
    value: str,
    value_type: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> SetResult:
    """Set an OID value. value_type: 'int' | 'str' | 'hex'."""
    if value_type not in ("int", "str", "hex"):
        return {
            "error": f"Unknown type '{value_type}'. Use int, str, or hex.",
            "host": host,
            "oid": oid,
        }

    type_map: dict[str, Any] = {
        "int": lambda: Integer(int(value)),
        "str": lambda: OctetString(value),
        "hex": lambda: OctetString(hexValue=value),
    }
    try:
        snmp_value = type_map[value_type]()
    except (ValueError, TypeError) as exc:
        return {"error": f"Invalid value for type '{value_type}': {exc}", "host": host, "oid": oid}

    return asyncio.run(
        _set_oid_with_transport(host, oid, snmp_value, value, usm, port, timeout, retries)
    )
```

- [ ] **Step 4: Remove `_transport` helper and old section comments**

Now that ALL public functions use the async path, remove:
- The `_transport()` function
- The `# Sync wrappers around the async pysnmp v7 API` section comment
- The `# Transport helper` section comment

Update the section comment above async internals to:
```python
# ---------------------------------------------------------------------------
# Async internals — reusable from other async contexts (e.g. bulk_check).
# The _*_cmd_async aliases above are the mock targets in tests.
# ---------------------------------------------------------------------------
```

- [ ] **Step 5: Run full query test suite + lint**

Run: `uv run pytest tests/test_query.py -v && uv run ruff check src/snmpv3_utils/core/query.py && uv run ruff format src/snmpv3_utils/core/query.py tests/test_query.py`
Expected: All pass, no lint errors

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py
git commit -m "refactor(query): extract async _set_oid, remove sync wrappers and _transport (#5)"
```

---

## Task 6: Refactor auth.py — Add `_check_creds_async` and `_parse_row_to_usm`

**Files:**
- Modify: `src/snmpv3_utils/core/auth.py`
- Modify: `tests/test_auth.py`

Extract the CSV row parsing into a helper, and create the async credential checker that calls `_get` from query.py.

- [ ] **Step 1: Write test for `_parse_row_to_usm`**

```python
# tests/test_auth.py — add at end
from snmpv3_utils.core.auth import _parse_row_to_usm


class TestParseRowToUsm:
    def test_valid_authpriv_row(self):
        row = {
            "username": "admin",
            "auth_protocol": "SHA256",
            "auth_key": "authpass",
            "priv_protocol": "AES128",
            "priv_key": "privpass",
            "security_level": "authPriv",
        }
        usm = _parse_row_to_usm(row)
        assert usm.userName == b"admin"

    def test_valid_noauthnopriv_row(self):
        row = {
            "username": "public",
            "auth_protocol": "",
            "auth_key": "",
            "priv_protocol": "",
            "priv_key": "",
            "security_level": "noAuthNoPriv",
        }
        usm = _parse_row_to_usm(row)
        assert usm.userName == b"public"

    def test_invalid_auth_protocol_raises(self):
        row = {
            "username": "bad",
            "auth_protocol": "SHA384",
            "auth_key": "key",
            "priv_protocol": "AES128",
            "priv_key": "priv",
            "security_level": "authPriv",
        }
        with pytest.raises(ValueError):
            _parse_row_to_usm(row)

    def test_missing_auth_key_raises(self):
        row = {
            "username": "bad",
            "auth_protocol": "SHA256",
            "auth_key": "",
            "priv_protocol": "AES128",
            "priv_key": "priv",
            "security_level": "authPriv",
        }
        with pytest.raises(ValueError):
            _parse_row_to_usm(row)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py::TestParseRowToUsm -v`
Expected: FAIL — `_parse_row_to_usm` does not exist yet

- [ ] **Step 3: Implement `_parse_row_to_usm` and `_check_creds_async`**

In `src/snmpv3_utils/core/auth.py`, add/update imports:

```python
from __future__ import annotations

import asyncio
import csv
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pysnmp.hlapi.v3arch.asyncio import UdpTransportTarget, UsmUserData

from snmpv3_utils.core.query import _get, get
from snmpv3_utils.security import (
    AuthProtocol,
    Credentials,
    PrivProtocol,
    SecurityLevel,
    build_usm_user,
)
from snmpv3_utils.types import AuthResult, VarBindError

if TYPE_CHECKING:
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
```

Note: `UdpTransportTarget` must be a runtime import (not `TYPE_CHECKING`-only) because `_bulk_check_async` calls `UdpTransportTarget.create(...)` at runtime, and tests patch it at `snmpv3_utils.core.auth.UdpTransportTarget.create`. `SnmpEngine` can stay under `TYPE_CHECKING` since it's only used in type annotations (with `from __future__ import annotations` making those lazy).

Extract the CSV row parsing logic from `bulk_check` into a helper:

```python
def _parse_row_to_usm(row: dict[str, str]) -> UsmUserData:
    """Parse a CSV row dict into a UsmUserData object.

    Raises ValueError on invalid enum values or missing required fields.
    """
    raw_auth = row.get("auth_protocol")
    raw_priv = row.get("priv_protocol")
    auth_proto = AuthProtocol(raw_auth) if raw_auth else None
    priv_proto = PrivProtocol(raw_priv) if raw_priv else None
    sec_level = SecurityLevel(row.get("security_level", "noAuthNoPriv"))
    creds = Credentials(
        username=row.get("username", ""),
        auth_protocol=auth_proto,
        auth_key=row.get("auth_key") or None,
        priv_protocol=priv_proto,
        priv_key=row.get("priv_key") or None,
        security_level=sec_level,
    )
    return build_usm_user(creds)
```

Add `_check_creds_async`:

```python
async def _check_creds_async(
    engine: SnmpEngine,
    host: str,
    usm: UsmUserData,
    username: str,
    transport: UdpTransportTarget,
) -> AuthResult:
    """Async credential check: GET sysDescr using pre-built engine + transport."""
    result = await _get(engine, host, _SYSDESCR_OID, usm, transport)
    if "error" in result:
        err = cast(VarBindError, result)
        return {"status": "failed", "host": host, "username": username, "error": err["error"]}
    return {"status": "ok", "host": host, "username": username, "sysdescr": result["value"]}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_auth.py::TestParseRowToUsm -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All PASS (existing tests unchanged, `check_creds` and `bulk_check` still work via sync path)

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/auth.py tests/test_auth.py
git commit -m "refactor(auth): extract _parse_row_to_usm and _check_creds_async (#5, #6)"
```

---

## Task 7: Implement `_bulk_check_async` with `asyncio.gather`

**Files:**
- Modify: `src/snmpv3_utils/core/auth.py`
- Modify: `tests/test_auth.py`

This is the core parallelization change. All existing `TestBulkCheck` tests must be updated because `bulk_check` will now go through the async path (`_bulk_check_async` → `_check_creds_async` → `_get`) instead of the sync path (`check_creds` → `get`).

- [ ] **Step 1: Update ALL existing TestBulkCheck tests to mock the async path**

The existing tests mock `check_creds`. After the refactor, `bulk_check` calls `_bulk_check_async` which uses `_get` (async). Update all three existing tests:

```python
from unittest.mock import AsyncMock, patch


class TestBulkCheck:
    def _make_csv(self, rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "username",
                "auth_protocol",
                "auth_key",
                "priv_protocol",
                "priv_key",
                "security_level",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_bulk_returns_result_per_row(self, mock_get, mock_transport, tmp_path):
        mock_transport.return_value = MagicMock()
        mock_get.side_effect = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
            {"error": "wrongDigest", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"},
        ]
        csv_content = self._make_csv(
            [
                {
                    "username": "admin",
                    "auth_protocol": "SHA256",
                    "auth_key": "pass",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
                {
                    "username": "wrong",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "failed"
        assert all(
            set(r.keys())
            in ({"status", "host", "username", "sysdescr"}, {"status", "host", "username", "error"})
            for r in results
        )

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    def test_bulk_returns_failed_on_invalid_credentials(self, mock_transport, tmp_path):
        """Rows with invalid credential combinations return status=failed without raising."""
        mock_transport.return_value = MagicMock()
        csv_content = self._make_csv(
            [
                {
                    "username": "bad",
                    "auth_protocol": "SHA256",
                    "auth_key": "",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "error" in results[0]

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    def test_bulk_handles_invalid_enum_in_csv(self, mock_transport, tmp_path):
        """Unrecognised enum values in CSV are returned as per-row failures."""
        mock_transport.return_value = MagicMock()
        csv_content = self._make_csv(
            [
                {
                    "username": "bad",
                    "auth_protocol": "SHA384",
                    "auth_key": "key",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "error" in results[0]
```

- [ ] **Step 2: Write new concurrency tests**

```python
class TestBulkCheckConcurrency:
    """Tests for the async gather path in bulk_check."""

    def _make_csv(self, rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "username",
                "auth_protocol",
                "auth_key",
                "priv_protocol",
                "priv_key",
                "security_level",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_results_preserve_csv_row_order(self, mock_get, mock_transport, tmp_path):
        """Results come back in CSV row order regardless of completion order."""
        mock_transport.return_value = MagicMock()
        mock_get.side_effect = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-A"},
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-B"},
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-C"},
        ]
        csv_content = self._make_csv(
            [
                {"username": "a", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
                {"username": "b", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
                {"username": "c", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 3
        assert results[0]["username"] == "a"
        assert results[1]["username"] == "b"
        assert results[2]["username"] == "c"

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_invalid_rows_inline_with_valid(self, mock_get, mock_transport, tmp_path):
        """Invalid CSV rows produce error results at their original index."""
        mock_transport.return_value = MagicMock()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        csv_content = self._make_csv(
            [
                {"username": "good", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
                {"username": "bad", "auth_protocol": "SHA384", "auth_key": "k",
                 "priv_protocol": "AES128", "priv_key": "p", "security_level": "authPriv"},
                {"username": "good2", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 3
        assert results[0]["status"] == "ok"
        assert results[0]["username"] == "good"
        assert results[1]["status"] == "failed"
        assert results[1]["username"] == "bad"
        assert "error" in results[1]
        assert results[2]["status"] == "ok"
        assert results[2]["username"] == "good2"

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_max_concurrent_none_runs_all(self, mock_get, mock_transport, tmp_path):
        """max_concurrent=None fires all checks without a semaphore."""
        mock_transport.return_value = MagicMock()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        csv_content = self._make_csv(
            [
                {"username": f"user{i}", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"}
                for i in range(5)
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path, max_concurrent=None)
        assert len(results) == 5
        assert all(r["status"] == "ok" for r in results)

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_max_concurrent_limits_parallelism(self, mock_get, mock_transport, tmp_path):
        """max_concurrent=2 limits how many checks run at once."""
        mock_transport.return_value = MagicMock()
        peak = 0
        current = 0

        async def _tracking_get(*args, **kwargs):
            nonlocal peak, current
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0)  # yield to event loop
            result = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
            current -= 1
            return result

        mock_get.side_effect = _tracking_get
        csv_content = self._make_csv(
            [
                {"username": f"user{i}", "auth_protocol": "", "auth_key": "",
                 "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"}
                for i in range(5)
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path, max_concurrent=2)
        assert len(results) == 5
        assert all(r["status"] == "ok" for r in results)
        assert peak <= 2
```

Add `import asyncio` at top of test file for the semaphore test.

- [ ] **Step 3: Run new tests to verify they fail**

Run: `uv run pytest tests/test_auth.py::TestBulkCheckConcurrency -v`
Expected: FAIL — `bulk_check` doesn't accept `max_concurrent` yet

- [ ] **Step 4: Implement `_bulk_check_async` and update `bulk_check`**

Replace the current `bulk_check` in `auth.py` with:

```python
_DEFAULT_MAX_CONCURRENT = 10


async def _bulk_check_async(
    host: str,
    csv_path: Path,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
) -> list[AuthResult]:
    """Async bulk credential check with optional concurrency limit."""
    from pysnmp.hlapi.v3arch.asyncio import SnmpEngine

    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (host, port), timeout=timeout, retries=retries
        )
    except Exception as exc:
        # Transport creation failed — return all-failed for every CSV row
        with open(csv_path, newline="") as f:
            rows = list(csv.DictReader(f))
        return [
            {
                "status": "failed",
                "host": host,
                "username": row.get("username", ""),
                "error": str(exc),
            }
            for row in rows
        ]

    sem = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    results: list[AuthResult | None] = [None] * len(rows)
    tasks: list[tuple[int, asyncio.Task[AuthResult]]] = []

    for i, row in enumerate(rows):
        try:
            usm = _parse_row_to_usm(row)
        except ValueError as e:
            results[i] = {
                "status": "failed",
                "host": host,
                "username": row.get("username", ""),
                "error": str(e),
            }
            continue

        async def _check_one(
            usm: UsmUserData = usm, username: str = row.get("username", "")
        ) -> AuthResult:
            if sem:
                async with sem:
                    return await _check_creds_async(engine, host, usm, username, transport)
            return await _check_creds_async(engine, host, usm, username, transport)

        tasks.append((i, asyncio.create_task(_check_one())))

    if tasks:
        gathered = await asyncio.gather(*(t for _, t in tasks))
        for (i, _), result in zip(tasks, gathered):
            results[i] = result

    return results  # type: ignore[return-value]


def bulk_check(
    host: str,
    csv_path: Path,
    max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
) -> list[AuthResult]:
    """Test every credential row in a CSV against a single host.

    CSV format: username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
    Returns a list of check_creds results, one per row.

    max_concurrent: max parallel SNMP checks (default 10). None = no limit.
    """
    return asyncio.run(
        _bulk_check_async(host, csv_path, max_concurrent=max_concurrent)
    )
```

- [ ] **Step 5: Run all auth tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All PASS (existing + new tests)

- [ ] **Step 6: Lint and format**

Run: `uv run ruff check src/snmpv3_utils/core/auth.py && uv run ruff format src/snmpv3_utils/core/auth.py tests/test_auth.py`
Expected: Clean

- [ ] **Step 7: Commit**

```bash
git add src/snmpv3_utils/core/auth.py tests/test_auth.py
git commit -m "feat(auth): parallelize bulk_check with asyncio.gather (#6)"
```

---

## Task 8: Full Verification

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors

- [ ] **Step 3: Run formatter**

Run: `uv run ruff format . --check`
Expected: No changes needed

- [ ] **Step 4: Run type checker**

Run: `uv run mypy src/`
Expected: No errors. Watch for:
- `_get` import in auth.py (private function cross-module import — mypy allows this)
- `AsyncMock` usage in tests (should be fine with Python 3.11+)
- `results: list[AuthResult | None]` with `type: ignore[return-value]` on final return
- `from __future__ import annotations` in auth.py for forward refs

- [ ] **Step 5: Run CLI smoke test**

Run: `uv run snmpv3 --help` and `uv run snmpv3 auth --help`
Expected: Help text displays correctly, no import errors

- [ ] **Step 6: Commit any final fixes**

If any lint/type/format fixes were needed:
```bash
git add -u
git commit -m "chore: fix lint/type issues from async refactor (#5, #6)"
```
