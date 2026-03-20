# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
