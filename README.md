# snmpv3-utils

A Python CLI for SNMPv3 testing. Most existing tools only support v1/v2 — this one does v3 properly.

## Install

```bash
pipx install snmpv3-utils
```

## Quick Start

```bash
# GET a single OID
snmpv3 query get 192.168.1.1 1.3.6.1.2.1.1.1.0 \
  --username admin \
  --auth-protocol SHA256 --auth-key myauthpass \
  --priv-protocol AES128 --priv-key myprivpass \
  --security-level authPriv

# WALK the system MIB
snmpv3 query walk 192.168.1.1 1.3.6.1.2.1.1 --profile myrouter

# Send a trap
snmpv3 trap send 192.168.1.1 --profile myrouter

# Test credentials
snmpv3 auth check 192.168.1.1 --profile myrouter

# Bulk test from a CSV
snmpv3 auth bulk 192.168.1.1 --file creds.csv

# JSON output (for piping into jq)
snmpv3 query walk 192.168.1.1 1.3.6.1.2.1.1 --format json | jq '.[] | .value'
```

## Configuration

Copy `.env.example` to `.env` and fill in your defaults:

```bash
cp .env.example .env
```

Or use named profiles:

```bash
snmpv3 profile add myrouter \
  --username admin \
  --auth-protocol SHA256 --auth-key myauthpass \
  --priv-protocol AES128 --priv-key myprivpass \
  --security-level authPriv
```

## Commands

| Group | Command | Description |
|-------|---------|-------------|
| `query` | `get` | Fetch a single OID |
| `query` | `getnext` | Single GETNEXT step |
| `query` | `walk` | Full subtree traversal |
| `query` | `bulk` | GETBULK retrieval |
| `query` | `set` | Set an OID value |
| `trap` | `send` | Send a trap or inform |
| `trap` | `listen` | Listen for incoming traps |
| `auth` | `check` | Test a credential set |
| `auth` | `bulk` | Test many credentials from CSV |
| `profile` | `add/delete/list/show` | Manage credential profiles |

## Supported Security

| Level | Auth | Privacy |
|-------|------|---------|
| noAuthNoPriv | — | — |
| authNoPriv | MD5, SHA1, SHA256, SHA512 | — |
| authPriv | MD5, SHA1, SHA256, SHA512 | DES, AES128, AES256 |

## License

MIT
