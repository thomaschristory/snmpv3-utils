# Async Core Internals + Parallel bulk_check

**Issues:** #5 (reuse SnmpEngine), #6 (parallelize bulk_check)

**Goal:** Extract async internals from `core/query.py` so that a single `SnmpEngine` and `UdpTransportTarget` can be reused across operations, then leverage `asyncio.gather()` in `bulk_check` to test credentials concurrently.

**Approach:** Async core internals with extended (not changed) sync public API. No CLI, output, security, or type changes.

---

## Architecture

### core/query.py

Each public function (`get`, `getnext`, `walk`, `bulk`, `set_oid`) gets a corresponding private async function (`_get`, `_getnext`, `_walk`, `_bulk`, `_set_oid`) that:

- Accepts `SnmpEngine`, `host: str`, `UsmUserData`, and `UdpTransportTarget` as parameters (no creation inside)
- Calls the pysnmp async API directly (`_get_cmd_async`, `_next_cmd_async`, etc.)
- Handles errors and returns the same TypedDict result types

The existing sync wrappers (`getCmd`, `nextCmd`, `setCmd`, `walkCmd`, `bulkCmd`) are removed. They existed to bridge sync/async — that bridge now lives in the public functions directly.

The sync `_transport()` helper is removed (no other module imports it). Async functions use `await UdpTransportTarget.create(...)` directly.

**Public sync API pattern — single `asyncio.run()` call:**

Each sync wrapper creates engine + transport + executes the query inside a single async function, avoiding the "different event loop" problem that would occur with multiple `asyncio.run()` calls:

```python
async def _get(engine: SnmpEngine, host: str, oid: str, usm: UsmUserData,
               transport: UdpTransportTarget) -> VarBindResult:
    error_indication, error_status, _, var_binds = await _get_cmd_async(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
    )
    if error_indication:
        return {"error": str(error_indication), "host": host, "oid": oid}
    if error_status:
        return {"error": str(error_status), "host": host, "oid": oid}
    return _var_bind_to_dict(var_binds[0])

async def _get_with_transport(host: str, oid: str, usm: UsmUserData,
                               port: int, timeout: int,
                               retries: int) -> VarBindResult:
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, port),
                                                timeout=timeout, retries=retries)
    return await _get(engine, host, oid, usm, transport)

def get(host: str, oid: str, usm: UsmUserData,
        port: int = 161, timeout: int = 5, retries: int = 3) -> VarBindResult:
    return asyncio.run(_get_with_transport(host, oid, usm, port, timeout, retries))
```

The two-level split (`_get` vs `_get_with_transport`) exists so that `_get` can be called from other async contexts (like `_bulk_check_async`) that already have an engine and transport, while `_get_with_transport` is the self-contained version for the sync API.

**walk and bulk async variants:** `_walk` uses `async for` on `_walk_cmd_async`, checking `error_indication or error_status` on each iteration and breaking on error (same as current `walk()`). `_bulk` awaits `_bulk_cmd_async`. Both pass `lexicographicMode=False` and collect results into lists internally, same as today. All keyword arguments from the current public functions are preserved in the async variants.

### core/auth.py

**`_check_creds_async`:** Async version of `check_creds` that accepts `engine`, `host`, `usm`, `username`, and `transport`. Calls `_get(engine, host, _SYSDESCR_OID, usm, transport)` (the async private function from `query.py`), **not** the sync public `get()` (which calls `asyncio.run()` and would fail inside a running loop). Returns `AuthResult`. No `port`/`timeout`/`retries` parameters — those are baked into the pre-built transport.

**`_bulk_check_async`:** Creates one `SnmpEngine`, one `UdpTransportTarget`, parses all CSV rows, then runs credential checks concurrently.

**SnmpEngine concurrent safety:** pysnmp v7's `SnmpEngine` holds mutable state (MIB controller, security subsystem). If concurrent operations on a shared engine cause issues, fall back to one engine per task — transport reuse alone still provides benefit. This must be verified during implementation.

**Row-order preservation:** Pre-allocate a `results: list[AuthResult]` of the same length as CSV rows. Invalid rows (bad enum, missing fields) get their error result written directly at their index. Valid rows produce `asyncio.gather()` tasks tagged with their index. After gather completes, write each result at its index. This guarantees CSV row order regardless of completion order.

```python
_DEFAULT_MAX_CONCURRENT = 10

async def _bulk_check_async(host: str, csv_path: Path,
                            max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT,
                            port: int = 161, timeout: int = 5,
                            retries: int = 1) -> list[AuthResult]:
    engine = SnmpEngine()
    transport = await UdpTransportTarget.create((host, port),
                                                timeout=timeout, retries=retries)
    # max_concurrent must be a positive int or None (no limit).
    # 0 is treated as None (no limit) due to falsy evaluation.
    sem = asyncio.Semaphore(max_concurrent) if max_concurrent else None

    # Parse CSV rows (newline="" per csv module docs)
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    results: list[AuthResult] = [None] * len(rows)  # type: ignore[list-item]
    tasks: list[tuple[int, asyncio.Task]] = []

    for i, row in enumerate(rows):
        try:
            # Extracted helper: parses CSV row dict -> Credentials -> build_usm_user()
            # Contains the same logic as the current inline parsing in bulk_check
            # (AuthProtocol/PrivProtocol/SecurityLevel enum construction, build_usm_user call)
            usm = _parse_row_to_usm(row)
        except ValueError as e:
            results[i] = {"status": "failed", "host": host,
                          "username": row.get("username", ""), "error": str(e)}
            continue

        async def _check_one(usm=usm, username=row.get("username", "")):
            if sem:
                async with sem:
                    return await _check_creds_async(engine, host, usm, username, transport)
            return await _check_creds_async(engine, host, usm, username, transport)

        tasks.append((i, asyncio.create_task(_check_one())))

    gathered = await asyncio.gather(*(t for _, t in tasks))
    for (i, _), result in zip(tasks, gathered):
        results[i] = result

    return results
```

**Public sync API (extended, not changed):**

```python
def bulk_check(host: str, csv_path: Path,
               max_concurrent: int | None = _DEFAULT_MAX_CONCURRENT) -> list[AuthResult]:
    return asyncio.run(_bulk_check_async(host, csv_path,
                                         max_concurrent=max_concurrent))
```

The `max_concurrent` parameter is new (default 10). Existing callers pass no value and get the default — backwards compatible. The CLI `auth bulk-check` command does not expose this parameter yet; that is deferred to issue #4 (trap stress).

**Concurrency control:**
- `max_concurrent=10` (default): sensible limit for normal credential testing, avoids flooding the target
- `max_concurrent=None`: no limit, all checks fire at once — intended for stress testing scenarios
- Future `trap stress` (#4) can reuse the same async internals with no concurrency cap

### core/trap.py

No changes. `_make_udp_target` stays (trap has its own sync transport construction). The async internals built here will benefit trap listen (#1) in a future PR.

---

## Files Changed

| File | Change |
|------|--------|
| `core/query.py` | Add `_get`, `_getnext`, `_walk`, `_bulk`, `_set_oid` async functions + `_*_with_transport` wrappers. Remove `getCmd`, `nextCmd`, `setCmd`, `walkCmd`, `bulkCmd` sync wrappers. Remove `_transport` helper. Public sync API calls single `asyncio.run()` on `_*_with_transport`. |
| `core/auth.py` | Add `_check_creds_async`, `_bulk_check_async`. `bulk_check` gains optional `max_concurrent` parameter (default 10). |
| `tests/test_query.py` | Update mocks: patch pysnmp async functions (`_get_cmd_async` etc.) using `AsyncMock` instead of removed sync wrappers. Same test assertions. |
| `tests/test_auth.py` | Add tests: row order preserved under concurrency, semaphore respected, no-limit mode, invalid rows still inline. New concurrency tests mock at pysnmp async level with `AsyncMock`. |

## Files NOT Changed

- `cli/` — calls same public sync functions (no `max_concurrent` CLI flag yet)
- `security.py` — untouched
- `output.py` — untouched
- `types.py` — no new types
- `core/trap.py` — untouched (future benefit)

---

## Testing Strategy

**Existing tests:** Update mock targets from removed sync wrappers to pysnmp async functions. The new patch paths are the module-level async aliases already in `query.py` (e.g., `snmpv3_utils.core.query._get_cmd_async` instead of `snmpv3_utils.core.query.getCmd`). Use `AsyncMock` (from `unittest.mock`) for async coroutine mocking. Same assertions, same coverage.

**New tests for bulk_check concurrency:**
1. Results preserve CSV row order when run concurrently
2. `max_concurrent=2` limits concurrent checks (verify via semaphore behavior)
3. `max_concurrent=None` runs all checks without limit
4. Invalid CSV rows produce inline error results (not lost during gather)

**Mock boundary:** Existing `test_auth.py` tests keep mocking at `check_creds` level. New concurrency tests mock at the pysnmp async function level with `AsyncMock` to verify the actual async gather path.

---

## Known Limitations

- **Nested event loops:** `asyncio.run()` raises `RuntimeError` if called from within an already-running event loop (e.g., Jupyter). This is the same limitation as the current code — not a regression. Future mitigation: expose async internals as a public async API, or use `nest_asyncio` as an opt-in.
- **SnmpEngine thread safety:** Must be verified during implementation. If concurrent operations on a shared engine cause issues, fall back to one engine per task.
