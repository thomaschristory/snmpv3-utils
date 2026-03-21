# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-03-21

### Changed
- Refactored all SNMP operations to async internals (`_get`, `_getnext`, `_walk`, `_bulk`, `_set_oid`) with `_*_with_transport` wrappers; public sync API unchanged
- `bulk_check` now runs credential checks in parallel via `asyncio.gather()` with a shared engine and transport
- Removed sync wrappers (`getCmd`, `nextCmd`, `setCmd`, `walkCmd`, `bulkCmd`) and `_transport` helper

### Added
- `max_concurrent` parameter on `bulk_check` (default 10, `None` = no limit) for concurrency control via `asyncio.Semaphore`
- `_parse_row_to_usm` helper for testable CSV row parsing
- `_check_creds_async` for async single-credential verification
- Transport failure and exception path tests for query and auth modules

### Fixed
- `_walk` now wraps async iteration in `try/except` consistent with other SNMP operations
- `asyncio.gather` uses `return_exceptions=True` so one task failure doesn't destroy all results
- CSV file is read once in `_bulk_check_async` instead of potentially twice
- `max_concurrent` validated to be a positive integer or `None`

## [0.1.1] - 2026-03-21

### Fixed
- Fix stale `_build_usm` docstring in `cli/_options.py` (#9)
- Use `TYPE_CHECKING` guard for `UsmUserData` import in `cli/_options.py` (#11)
- Re-export `UsmUserData` from `security.py` to maintain architecture boundary
- Replace TOCTOU file check with `try/except` in auth bulk CLI (#12)
- Widen error handling in `auth bulk` to catch `PermissionError`, `IsADirectoryError`, and `csv.Error`

### Changed
- Expand allowed commit prefixes to include `refactor:` and `style:` (#10)
- Allow `fix/`, `docs/`, `chore/` branch name prefixes in addition to `feat/`

### Added
- Test coverage for `auth bulk` CLI command (file-not-found and success paths)

## [0.1.0] - 2026-03-20

### Added
- Initial release with full SNMPv3 query, trap, and credential testing support
- `snmpv3 query` — GET, GETNEXT, WALK, BULK, SET
- `snmpv3 trap` — send (trap + inform), listen (stub, asyncio pending)
- `snmpv3 auth` — single credential check, bulk CSV check
- `snmpv3 profile` — add, delete, list, show profiles
- Full SNMPv3 security matrix: noAuthNoPriv, authNoPriv, authPriv
- Auth protocols: MD5, SHA1, SHA256, SHA512
- Priv protocols: DES, AES128, AES256
- Credential resolution: defaults → .env → profile → CLI flags
- Rich and JSON output via `--format` flag
