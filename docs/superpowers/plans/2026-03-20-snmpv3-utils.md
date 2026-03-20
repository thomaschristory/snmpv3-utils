# snmpv3-utils Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish a pipx-installable Python CLI for SNMPv3 operations (GET, GETNEXT, WALK, BULK, SET, trap send/listen, credential testing) with full security protocol support.

**Architecture:** Layered separation — `cli/` parses args and delegates, `core/` contains all SNMP logic returning plain dicts, `security.py` is the sole pysnmp-aware module, `output.py` formats for rich/JSON. Tests mock at the pysnmp hlapi function boundary (mock `getCmd`, `setCmd`, etc. directly).

**Tech Stack:** Python 3.11+, typer, rich, pysnmp 7 (lextudio), python-dotenv, platformdirs, ruff, mypy, pytest, uv, GitHub Actions

---

## File Map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Project metadata, dependencies, tool config (ruff, mypy, pytest) |
| `src/snmpv3_utils/security.py` | USM parameter builder — only file that imports pysnmp auth/priv constants |
| `src/snmpv3_utils/config.py` | Credentials dataclass, .env loading, profile read/write/list/delete |
| `src/snmpv3_utils/output.py` | Rich table formatters + JSON serializer — no SNMP, no CLI |
| `src/snmpv3_utils/core/query.py` | `get`, `getnext`, `walk`, `bulk`, `set` — return `dict`/`list[dict]` |
| `src/snmpv3_utils/core/trap.py` | `send_trap`, `listen` — return `dict`/yields `dict` |
| `src/snmpv3_utils/core/auth.py` | `check_creds`, `bulk_check` — return `dict`/`list[dict]` |
| `src/snmpv3_utils/cli/main.py` | Root typer app, registers all subcommand groups |
| `src/snmpv3_utils/cli/query.py` | Typer commands for `snmpv3 query *` |
| `src/snmpv3_utils/cli/trap.py` | Typer commands for `snmpv3 trap *` |
| `src/snmpv3_utils/cli/auth.py` | Typer commands for `snmpv3 auth *` |
| `src/snmpv3_utils/cli/profile.py` | Typer commands for `snmpv3 profile *` |
| `tests/conftest.py` | Shared fixtures (mock USM, sample responses) |
| `.github/workflows/ci.yml` | PR checks: ruff, mypy, pytest |
| `.github/workflows/release.yml` | Tag-triggered PyPI publish + GitHub Release |

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/snmpv3_utils/__init__.py`
- Create: `src/snmpv3_utils/cli/__init__.py`
- Create: `src/snmpv3_utils/core/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/` (empty dir with `.gitkeep`)
- Create: `.gitignore`
- Create: `.python-version`

- [ ] **Step 1: Create the directory tree**

```bash
mkdir -p src/snmpv3_utils/cli src/snmpv3_utils/core tests/fixtures
touch src/snmpv3_utils/__init__.py
touch src/snmpv3_utils/cli/__init__.py
touch src/snmpv3_utils/core/__init__.py
touch tests/__init__.py
touch tests/fixtures/.gitkeep
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "snmpv3-utils"
version = "0.1.0"
description = "SNMPv3 CLI testing utility — GET, WALK, SET, traps, credential testing"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
keywords = ["snmp", "snmpv3", "network", "cli", "testing"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Topic :: System :: Networking :: Monitoring",
]
dependencies = [
    "typer>=0.12",
    "rich>=13",
    "pysnmp>=7.0",
    "python-dotenv>=1.0",
    "platformdirs>=4.0",
    "tomli-w>=1.2",
    "tomli>=2.0; python_version < '3.11'",
]

[project.scripts]
snmpv3 = "snmpv3_utils.cli.main:app"

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "mypy>=1.9",
    "ruff>=0.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/snmpv3_utils"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
strict = true
python_version = "3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

- [ ] **Step 3: Write `.python-version`**

```
3.11
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.venv/
dist/
*.egg-info/
.env
.mypy_cache/
.ruff_cache/
.pytest_cache/
```

- [ ] **Step 5: Initialize uv and install dependencies**

```bash
uv sync --all-extras
```

Expected: uv creates `.venv/` and installs all dependencies including dev extras.

- [ ] **Step 6: Verify the install worked**

```bash
uv run python -c "import typer, rich, pysnmp, dotenv, platformdirs; print('OK')"
```

Expected output: `OK`

- [ ] **Step 7: Initialize git and make first commit**

```bash
git init
git add .
git commit -m "chore: initial project scaffold"
```

---

## Task 2: GitHub Repository Setup

**Prerequisites:** GitHub CLI (`gh`) installed and authenticated (`gh auth status`).

- [ ] **Step 1: Get your GitHub username**

```bash
gh api user --jq .login
```

Note the output — you'll need it below.

- [ ] **Step 2: Create the public repo and push**

```bash
gh repo create snmpv3-utils \
  --public \
  --description "SNMPv3 CLI testing utility — GET, WALK, SET, traps, credential testing" \
  --source . \
  --remote origin \
  --push
```

Expected: repo created at `https://github.com/<your-username>/snmpv3-utils`

- [ ] **Step 3: Rename default branch to `main` if needed**

```bash
git branch -M main
git push -u origin main
```

- [ ] **Step 4: Enable branch protection on `main`**

Replace `OWNER` with your GitHub username:

```bash
gh api repos/OWNER/snmpv3-utils/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":0}' \
  --field restrictions=null
```

Note: `"contexts":["ci"]` references the job name in `ci.yml` — update this after Task 12 if the job name differs.

- [ ] **Step 5: Verify the repo is visible**

```bash
gh repo view --web
```

---

## Task 3: `security.py` — USM Parameter Builder

**Files:**
- Create: `src/snmpv3_utils/security.py`
- Create: `tests/test_security.py`

This is the only module that imports pysnmp auth/priv constants. Everything else receives a `UsmUserData` object.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_security.py
import pytest
from pysnmp.hlapi import UsmUserData
from snmpv3_utils.security import (
    AuthProtocol,
    PrivProtocol,
    SecurityLevel,
    Credentials,
    build_usm_user,
)


def test_no_auth_no_priv():
    creds = Credentials(username="public", security_level=SecurityLevel.NO_AUTH_NO_PRIV)
    usm = build_usm_user(creds)
    assert isinstance(usm, UsmUserData)


def test_auth_no_priv_sha256():
    creds = Credentials(
        username="monitor",
        auth_protocol=AuthProtocol.SHA256,
        auth_key="authpassword",
        security_level=SecurityLevel.AUTH_NO_PRIV,
    )
    usm = build_usm_user(creds)
    assert isinstance(usm, UsmUserData)
    assert usm.authKey == b"authpassword"


def test_auth_priv_sha256_aes128():
    creds = Credentials(
        username="admin",
        auth_protocol=AuthProtocol.SHA256,
        auth_key="authpassword",
        priv_protocol=PrivProtocol.AES128,
        priv_key="privpassword",
        security_level=SecurityLevel.AUTH_PRIV,
    )
    usm = build_usm_user(creds)
    assert isinstance(usm, UsmUserData)
    assert usm.privKey == b"privpassword"


def test_auth_priv_md5_des():
    creds = Credentials(
        username="legacy",
        auth_protocol=AuthProtocol.MD5,
        auth_key="authpass",
        priv_protocol=PrivProtocol.DES,
        priv_key="privpass",
        security_level=SecurityLevel.AUTH_PRIV,
    )
    usm = build_usm_user(creds)
    assert isinstance(usm, UsmUserData)


def test_auth_priv_sha512_aes256():
    creds = Credentials(
        username="secure",
        auth_protocol=AuthProtocol.SHA512,
        auth_key="authpass",
        priv_protocol=PrivProtocol.AES256,
        priv_key="privpass",
        security_level=SecurityLevel.AUTH_PRIV,
    )
    usm = build_usm_user(creds)
    assert isinstance(usm, UsmUserData)


def test_invalid_auth_priv_combination_raises():
    """authPriv requires both auth_key and priv_key."""
    creds = Credentials(
        username="bad",
        security_level=SecurityLevel.AUTH_PRIV,
        # missing auth_protocol, auth_key, priv_protocol, priv_key
    )
    with pytest.raises(ValueError, match="auth_protocol and auth_key required"):
        build_usm_user(creds)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_security.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `security.py` doesn't exist yet.

- [ ] **Step 3: Write `security.py`**

```python
# src/snmpv3_utils/security.py
"""SNMPv3 USM parameter builder.

This is the only module in snmpv3_utils that imports pysnmp auth/priv protocol
constants. All other modules receive a pre-built UsmUserData object.
"""
from dataclasses import dataclass, field
from enum import StrEnum

from pysnmp.hlapi import (
    UsmUserData,
    usmAesCfb128Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)


class AuthProtocol(StrEnum):
    MD5 = "MD5"
    SHA1 = "SHA1"
    SHA256 = "SHA256"
    SHA512 = "SHA512"


class PrivProtocol(StrEnum):
    DES = "DES"
    AES128 = "AES128"
    AES256 = "AES256"


class SecurityLevel(StrEnum):
    NO_AUTH_NO_PRIV = "noAuthNoPriv"
    AUTH_NO_PRIV = "authNoPriv"
    AUTH_PRIV = "authPriv"


_AUTH_PROTOCOL_MAP = {
    AuthProtocol.MD5: usmHMACMD5AuthProtocol,
    AuthProtocol.SHA1: usmHMACSHAAuthProtocol,
    AuthProtocol.SHA256: usmHMAC192SHA256AuthProtocol,
    AuthProtocol.SHA512: usmHMAC384SHA512AuthProtocol,
}

_PRIV_PROTOCOL_MAP = {
    PrivProtocol.DES: usmDESPrivProtocol,
    PrivProtocol.AES128: usmAesCfb128Protocol,
    PrivProtocol.AES256: usmAesCfb256Protocol,
}


@dataclass
class Credentials:
    """Holds all SNMPv3 credential fields. Use config.resolve_credentials() to build one."""

    username: str = ""
    auth_protocol: AuthProtocol | None = None
    auth_key: str | None = None
    priv_protocol: PrivProtocol | None = None
    priv_key: str | None = None
    security_level: SecurityLevel = SecurityLevel.NO_AUTH_NO_PRIV
    port: int = 161
    timeout: int = 5
    retries: int = 3


def build_usm_user(creds: Credentials) -> UsmUserData:
    """Build a pysnmp UsmUserData from a Credentials object.

    Raises ValueError if the security_level requires fields that are missing.
    """
    level = creds.security_level

    if level == SecurityLevel.NO_AUTH_NO_PRIV:
        return UsmUserData(
            creds.username,
            authProtocol=usmNoAuthProtocol,
            privProtocol=usmNoPrivProtocol,
        )

    if level in (SecurityLevel.AUTH_NO_PRIV, SecurityLevel.AUTH_PRIV):
        if not creds.auth_protocol or not creds.auth_key:
            raise ValueError("auth_protocol and auth_key required for authNoPriv/authPriv")

    if level == SecurityLevel.AUTH_NO_PRIV:
        return UsmUserData(
            creds.username,
            authKey=creds.auth_key,
            authProtocol=_AUTH_PROTOCOL_MAP[creds.auth_protocol],  # type: ignore[index]
            privProtocol=usmNoPrivProtocol,
        )

    # AUTH_PRIV
    if not creds.priv_protocol or not creds.priv_key:
        raise ValueError("priv_protocol and priv_key required for authPriv")

    return UsmUserData(
        creds.username,
        authKey=creds.auth_key,
        authProtocol=_AUTH_PROTOCOL_MAP[creds.auth_protocol],  # type: ignore[index]
        privKey=creds.priv_key,
        privProtocol=_PRIV_PROTOCOL_MAP[creds.priv_protocol],
    )
```

> **pysnmp v7 note:** If any import fails (e.g. `usmHMAC192SHA256AuthProtocol`), check
> `pysnmp.hlapi.__all__` or the [pysnmp lextudio docs](https://pysnmp.readthedocs.io) for the
> correct constant names in your installed version. The SHA-256 constant name varies between
> pysnmp releases.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_security.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Run mypy and ruff**

```bash
uv run mypy src/snmpv3_utils/security.py
uv run ruff check src/snmpv3_utils/security.py
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/security.py tests/test_security.py
git commit -m "feat: add security module with USM parameter builder"
```

---

## Task 4: `config.py` — Credentials Resolution & Profile Management

**Files:**
- Create: `src/snmpv3_utils/config.py`
- Create: `tests/test_config.py`
- Create: `.env.example`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import os
from pathlib import Path

import pytest
import tomllib

from snmpv3_utils.config import (
    load_from_env,
    resolve_credentials,
    get_profiles_path,
    load_profile,
    save_profile,
    list_profiles,
    delete_profile,
)
from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel


def test_load_from_env_defaults(monkeypatch):
    """With no env vars set, returns Credentials with built-in defaults."""
    for key in [
        "SNMPV3_USERNAME", "SNMPV3_AUTH_PROTOCOL", "SNMPV3_AUTH_KEY",
        "SNMPV3_PRIV_PROTOCOL", "SNMPV3_PRIV_KEY", "SNMPV3_SECURITY_LEVEL",
        "SNMPV3_PORT", "SNMPV3_TIMEOUT", "SNMPV3_RETRIES",
    ]:
        monkeypatch.delenv(key, raising=False)

    creds = load_from_env()
    assert creds.username == ""
    assert creds.port == 161
    assert creds.timeout == 5
    assert creds.retries == 3
    assert creds.security_level == SecurityLevel.NO_AUTH_NO_PRIV


def test_load_from_env_reads_variables(monkeypatch):
    monkeypatch.setenv("SNMPV3_USERNAME", "admin")
    monkeypatch.setenv("SNMPV3_AUTH_PROTOCOL", "SHA256")
    monkeypatch.setenv("SNMPV3_AUTH_KEY", "myauthkey")
    monkeypatch.setenv("SNMPV3_PRIV_PROTOCOL", "AES128")
    monkeypatch.setenv("SNMPV3_PRIV_KEY", "myprivkey")
    monkeypatch.setenv("SNMPV3_SECURITY_LEVEL", "authPriv")
    monkeypatch.setenv("SNMPV3_PORT", "1161")
    monkeypatch.setenv("SNMPV3_TIMEOUT", "10")
    monkeypatch.setenv("SNMPV3_RETRIES", "1")

    creds = load_from_env()
    assert creds.username == "admin"
    assert creds.auth_protocol == AuthProtocol.SHA256
    assert creds.auth_key == "myauthkey"
    assert creds.priv_protocol == PrivProtocol.AES128
    assert creds.priv_key == "myprivkey"
    assert creds.security_level == SecurityLevel.AUTH_PRIV
    assert creds.port == 1161
    assert creds.timeout == 10
    assert creds.retries == 1


def test_resolve_credentials_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("SNMPV3_USERNAME", "from_env")
    monkeypatch.setenv("SNMPV3_PORT", "161")

    creds = resolve_credentials(cli_overrides={"username": "from_cli"})
    assert creds.username == "from_cli"


def test_profile_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")

    profile = Credentials(
        username="testuser",
        auth_protocol=AuthProtocol.SHA1,
        auth_key="authkey",
        security_level=SecurityLevel.AUTH_NO_PRIV,
        port=161,
        timeout=5,
        retries=3,
    )
    save_profile("myprofile", profile)

    loaded = load_profile("myprofile")
    assert loaded.username == "testuser"
    assert loaded.auth_protocol == AuthProtocol.SHA1
    assert loaded.security_level == SecurityLevel.AUTH_NO_PRIV


def test_list_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")

    save_profile("alpha", Credentials(username="a"))
    save_profile("beta", Credentials(username="b"))

    names = list_profiles()
    assert "alpha" in names
    assert "beta" in names


def test_delete_profile(tmp_path, monkeypatch):
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")

    save_profile("to_delete", Credentials(username="gone"))
    delete_profile("to_delete")

    assert "to_delete" not in list_profiles()


def test_load_nonexistent_profile_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")

    with pytest.raises(KeyError, match="nope"):
        load_profile("nope")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ImportError` — `config.py` doesn't exist yet.

- [ ] **Step 3: Write `config.py`**

```python
# src/snmpv3_utils/config.py
"""Credential resolution and profile management.

Resolution order (lowest to highest priority):
  built-in defaults → env vars / .env file → named profile → CLI flags
"""
import os
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from platformdirs import user_config_dir

from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel

_PROFILE_FILE_VERSION = 1


def get_profiles_path() -> Path:
    """Return the platform-appropriate path for profiles.toml."""
    return Path(user_config_dir("snmpv3utils")) / "profiles.toml"


def load_from_env() -> Credentials:
    """Read SNMPv3_* environment variables (and .env file) into a Credentials object."""
    load_dotenv()

    raw_auth = os.getenv("SNMPV3_AUTH_PROTOCOL")
    raw_priv = os.getenv("SNMPV3_PRIV_PROTOCOL")
    raw_level = os.getenv("SNMPV3_SECURITY_LEVEL", "noAuthNoPriv")

    return Credentials(
        username=os.getenv("SNMPV3_USERNAME", ""),
        auth_protocol=AuthProtocol(raw_auth) if raw_auth else None,
        auth_key=os.getenv("SNMPV3_AUTH_KEY"),
        priv_protocol=PrivProtocol(raw_priv) if raw_priv else None,
        priv_key=os.getenv("SNMPV3_PRIV_KEY"),
        security_level=SecurityLevel(raw_level),
        port=int(os.getenv("SNMPV3_PORT", "161")),
        timeout=int(os.getenv("SNMPV3_TIMEOUT", "5")),
        retries=int(os.getenv("SNMPV3_RETRIES", "3")),
    )


def load_profile(name: str) -> Credentials:
    """Load a named profile from profiles.toml. Raises KeyError if not found."""
    path = get_profiles_path()
    if not path.exists():
        raise KeyError(name)

    with open(path, "rb") as f:
        data = tomllib.load(f)

    profiles = data.get("profiles", {})
    if name not in profiles:
        raise KeyError(name)

    p = profiles[name]
    return Credentials(
        username=p.get("username", ""),
        auth_protocol=AuthProtocol(p["auth_protocol"]) if p.get("auth_protocol") else None,
        auth_key=p.get("auth_key"),
        priv_protocol=PrivProtocol(p["priv_protocol"]) if p.get("priv_protocol") else None,
        priv_key=p.get("priv_key"),
        security_level=SecurityLevel(p.get("security_level", "noAuthNoPriv")),
        port=int(p.get("port", 161)),
        timeout=int(p.get("timeout", 5)),
        retries=int(p.get("retries", 3)),
    )


def save_profile(name: str, creds: Credentials) -> None:
    """Save or overwrite a named profile in profiles.toml."""
    import tomli_w  # type: ignore[import]

    path = get_profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.exists():
        with open(path, "rb") as f:
            existing = tomllib.load(f)

    existing.setdefault("profiles", {})
    existing["profiles"][name] = {
        k: (v.value if hasattr(v, "value") else v)
        for k, v in asdict(creds).items()
        if v is not None
    }

    with open(path, "wb") as f:
        tomli_w.dump(existing, f)


def list_profiles() -> list[str]:
    """Return all profile names, or an empty list if no profiles file exists."""
    path = get_profiles_path()
    if not path.exists():
        return []
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return list(data.get("profiles", {}).keys())


def delete_profile(name: str) -> None:
    """Remove a profile. Silently does nothing if the profile doesn't exist."""
    import tomli_w  # type: ignore[import]

    path = get_profiles_path()
    if not path.exists():
        return
    with open(path, "rb") as f:
        data = tomllib.load(f)
    data.get("profiles", {}).pop(name, None)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def resolve_credentials(
    profile_name: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Credentials:
    """Merge credentials: defaults → env → profile → CLI flags.

    cli_overrides: dict of Credentials field names to values (None values are ignored).
    """
    base = load_from_env()

    if profile_name:
        profile = load_profile(profile_name)
        # Profile fields overwrite env fields where the profile has a non-default value
        base = _merge(base, profile)

    if cli_overrides:
        base = _merge(base, Credentials(**{k: v for k, v in cli_overrides.items() if v is not None}))

    return base


def _merge(base: Credentials, override: Credentials) -> Credentials:
    """Return a new Credentials with non-default values from override applied to base."""
    default = Credentials()
    result = Credentials(**{**asdict(base)})
    for field, value in asdict(override).items():
        if value != getattr(default, field):
            setattr(result, field, value)
    return result
```

> **Note:** `save_profile` and `delete_profile` require `tomli-w`. Add it to dependencies:
>
> ```bash
> uv add tomli-w
> ```

- [ ] **Step 4: Add `tomli-w` dependency**

```bash
uv add tomli-w
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run pytest tests/test_config.py -v
```

Expected: all 7 tests pass.

- [ ] **Step 6: Write `.env.example`**

```ini
# .env.example — copy to .env and fill in your values
# SNMPv3 credentials
SNMPV3_USERNAME=
SNMPV3_AUTH_PROTOCOL=SHA256     # MD5 | SHA1 | SHA256 | SHA512
SNMPV3_AUTH_KEY=
SNMPV3_PRIV_PROTOCOL=AES128     # DES | AES128 | AES256
SNMPV3_PRIV_KEY=
SNMPV3_SECURITY_LEVEL=authPriv  # noAuthNoPriv | authNoPriv | authPriv

# Connection defaults
SNMPV3_PORT=161
SNMPV3_TIMEOUT=5
SNMPV3_RETRIES=3
```

- [ ] **Step 7: Run mypy and ruff**

```bash
uv run mypy src/snmpv3_utils/config.py
uv run ruff check src/snmpv3_utils/config.py
```

- [ ] **Step 8: Commit**

```bash
git add src/snmpv3_utils/config.py tests/test_config.py .env.example pyproject.toml uv.lock
git commit -m "feat: add config module with credential resolution and profile management"
```

---

## Task 5: `output.py` — Rich & JSON Formatting

**Files:**
- Create: `src/snmpv3_utils/output.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_output.py
import json

import pytest
from rich.console import Console

from snmpv3_utils.output import OutputFormat, print_records, print_single, print_error


def test_print_single_json(capsys):
    print_single({"oid": "1.3.6.1", "value": "Linux"}, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["oid"] == "1.3.6.1"
    assert data["value"] == "Linux"


def test_print_records_json(capsys):
    records = [
        {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
        {"oid": "1.3.6.1.2.1.1.2.0", "value": "1.3.6.1"},
    ]
    print_records(records, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2
    assert data[0]["oid"] == "1.3.6.1.2.1.1.1.0"


def test_print_error_json(capsys):
    print_error({"error": "Timeout", "host": "192.168.1.1"}, fmt=OutputFormat.JSON)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["error"] == "Timeout"


def test_print_single_rich_does_not_crash():
    """Rich output should not raise — we don't assert exact text, just no exceptions."""
    console = Console(force_terminal=False)
    print_single({"oid": "1.3.6.1", "value": "Linux"}, fmt=OutputFormat.RICH, console=console)


def test_print_records_rich_does_not_crash():
    console = Console(force_terminal=False)
    records = [{"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}]
    print_records(records, fmt=OutputFormat.RICH, console=console)


def test_print_error_rich_does_not_crash():
    console = Console(force_terminal=False)
    print_error({"error": "Timeout"}, fmt=OutputFormat.RICH, console=console)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_output.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Write `output.py`**

```python
# src/snmpv3_utils/output.py
"""Output formatting — rich tables and JSON.

All functions accept an optional `console` parameter for testing.
The `fmt` parameter controls output format: RICH (default) or JSON.
"""
import json
import sys
from enum import StrEnum
from typing import Any

from rich.console import Console
from rich.table import Table
from rich import print as rprint

_default_console = Console()
_error_console = Console(stderr=True)


class OutputFormat(StrEnum):
    RICH = "rich"
    JSON = "json"


def print_single(
    record: dict[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a single result record."""
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _default_console
    table = Table(show_header=True, header_style="bold cyan")
    for key in record:
        table.add_column(key.capitalize())
    table.add_row(*[str(v) for v in record.values()])
    c.print(table)


def print_records(
    records: list[dict[str, Any]],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print a list of result records as a table or JSON array."""
    if not records:
        return
    if fmt == OutputFormat.JSON:
        print(json.dumps(records))
        return
    c = console or _default_console
    table = Table(show_header=True, header_style="bold cyan")
    for key in records[0]:
        table.add_column(key.capitalize())
    for record in records:
        table.add_row(*[str(v) for v in record.values()])
    c.print(table)


def print_error(
    record: dict[str, Any],
    fmt: OutputFormat = OutputFormat.RICH,
    console: Console | None = None,
) -> None:
    """Print an error record. Rich shows it in red on stderr; JSON goes to stdout."""
    if fmt == OutputFormat.JSON:
        print(json.dumps(record))
        return
    c = console or _error_console
    c.print(f"[bold red]Error:[/bold red] {record.get('error', record)}")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_output.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/output.py tests/test_output.py
git commit -m "feat: add output module for rich/JSON formatting"
```

---

## Task 6: `core/query.py` — SNMP Query Operations

**Files:**
- Create: `src/snmpv3_utils/core/query.py`
- Create: `tests/test_query.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `conftest.py` with shared fixtures**

```python
# tests/conftest.py
import pytest
from unittest.mock import MagicMock
from pysnmp.hlapi import UsmUserData, usmNoAuthProtocol, usmNoPrivProtocol
from pysnmp.smi.rfc1902 import ObjectType, ObjectIdentity
from pyasn1.type.univ import OctetString, Integer


@pytest.fixture
def usm_no_auth():
    return UsmUserData("public", authProtocol=usmNoAuthProtocol, privProtocol=usmNoPrivProtocol)


@pytest.fixture
def oid_sysdescr():
    return "1.3.6.1.2.1.1.1.0"


def make_mock_var_binds(oid: str, value: str) -> list:
    """Build a mock varBinds list as returned by pysnmp hlapi."""
    obj_type = MagicMock()
    obj_type.prettyPrint.return_value = value
    obj_type.__getitem__ = MagicMock(side_effect=lambda i: oid if i == 0 else obj_type)
    obj_type[0].prettyPrint = MagicMock(return_value=oid)
    obj_type[1].prettyPrint = MagicMock(return_value=value)
    return [obj_type]
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_query.py
from unittest.mock import patch, MagicMock

import pytest

from snmpv3_utils.core.query import get, getnext, walk, bulk, set_oid
from snmpv3_utils.security import Credentials, build_usm_user


@pytest.fixture
def usm(usm_no_auth):
    return usm_no_auth


def _mock_cmd_result(oid="1.3.6.1.2.1.1.1.0", value="Linux router"):
    """Return a single (errorIndication, errorStatus, errorIndex, varBinds) tuple."""
    var_bind = MagicMock()
    var_bind.__getitem__ = MagicMock(side_effect=lambda i: MagicMock(
        prettyPrint=MagicMock(return_value=oid if i == 0 else value)
    ))
    return [(None, None, None, [var_bind])]


class TestGet:
    @patch("snmpv3_utils.core.query.getCmd")
    def test_returns_dict_with_oid_and_value(self, mock_get, usm):
        mock_get.return_value = iter(_mock_cmd_result())
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert "value" in result

    @patch("snmpv3_utils.core.query.getCmd")
    def test_returns_error_dict_on_failure(self, mock_get, usm):
        var_bind = MagicMock()
        mock_get.return_value = iter([("Timeout", None, None, [])])
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result


class TestGetnext:
    @patch("snmpv3_utils.core.query.nextCmd")
    def test_returns_dict_with_next_oid(self, mock_next, usm):
        mock_next.return_value = iter(_mock_cmd_result(oid="1.3.6.1.2.1.1.2.0"))
        result = getnext("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result


class TestWalk:
    @patch("snmpv3_utils.core.query.walkCmd")
    def test_returns_list_of_dicts(self, mock_walk, usm):
        mock_walk.return_value = iter([
            (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.1.0", "Linux")[0][3]),
            (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.2.0", "sysObjectID")[0][3]),
        ])
        results = walk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)

    @patch("snmpv3_utils.core.query.walkCmd")
    def test_empty_walk_returns_empty_list(self, mock_walk, usm):
        mock_walk.return_value = iter([])
        results = walk("192.168.1.1", "1.3.6.1.2.1.99", usm)
        assert results == []


class TestBulk:
    @patch("snmpv3_utils.core.query.bulkCmd")
    def test_returns_list_of_dicts(self, mock_bulk, usm):
        mock_bulk.return_value = iter([
            (None, None, None, _mock_cmd_result()[0][3]),
        ])
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)


class TestSet:
    @patch("snmpv3_utils.core.query.setCmd")
    def test_returns_success_dict(self, mock_set, usm):
        mock_set.return_value = iter([(None, None, None, [])])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "myrouter", "str", usm)
        assert result.get("status") == "ok"

    @patch("snmpv3_utils.core.query.setCmd")
    def test_returns_error_on_failure(self, mock_set, usm):
        mock_set.return_value = iter([("noSuchObject", None, None, [])])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "x", "str", usm)
        assert "error" in result
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
uv run pytest tests/test_query.py -v
```

- [ ] **Step 4: Write `core/query.py`**

```python
# src/snmpv3_utils/core/query.py
"""SNMP query operations: GET, GETNEXT, WALK, BULK, SET.

All functions return plain dicts or list of dicts — no rich, no CLI.
Errors are returned as {"error": "<message>"} — never raised.
"""
from typing import Any

from pysnmp.hlapi import (
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    bulkCmd,
    getCmd,
    nextCmd,
    setCmd,
    walkCmd,
)
from pyasn1.type.univ import Integer, OctetString


def _transport(host: str, port: int, timeout: int, retries: int) -> UdpTransportTarget:
    return UdpTransportTarget((host, port), timeout=timeout, retries=retries)


def _var_bind_to_dict(var_bind: Any) -> dict[str, Any]:
    return {"oid": var_bind[0].prettyPrint(), "value": var_bind[1].prettyPrint()}


def get(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> dict[str, Any]:
    """Fetch a single OID value."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, var_binds in getCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return _var_bind_to_dict(var_binds[0])
    return {"error": "No response", "host": host, "oid": oid}


def getnext(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> dict[str, Any]:
    """Return the next OID after the given one (single GETNEXT step)."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, var_binds in nextCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid))
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return _var_bind_to_dict(var_binds[0])
    return {"error": "No response", "host": host, "oid": oid}


def walk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> list[dict[str, Any]]:
    """Traverse the subtree rooted at oid via repeated GETNEXT."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    results = []
    for error_indication, error_status, _, var_binds in walkCmd(
        engine, usm, transport, ContextData(), ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append({"error": str(error_indication or error_status)})
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


def bulk(
    host: str,
    oid: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
    max_repetitions: int = 25,
) -> list[dict[str, Any]]:
    """GETBULK retrieval."""
    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    results = []
    for error_indication, error_status, _, var_binds in bulkCmd(
        engine, usm, transport, ContextData(),
        0, max_repetitions,
        ObjectType(ObjectIdentity(oid)),
        lexicographicMode=False,
    ):
        if error_indication or error_status:
            results.append({"error": str(error_indication or error_status)})
            break
        for vb in var_binds:
            results.append(_var_bind_to_dict(vb))
    return results


def set_oid(
    host: str,
    oid: str,
    value: str,
    value_type: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 3,
) -> dict[str, Any]:
    """Set an OID value. value_type: 'int' | 'str' | 'hex'."""
    type_map: dict[str, Any] = {
        "int": Integer(int(value)),
        "str": OctetString(value),
        "hex": OctetString(hexValue=value),
    }
    if value_type not in type_map:
        return {"error": f"Unknown type '{value_type}'. Use int, str, or hex."}

    engine = SnmpEngine()
    transport = _transport(host, port, timeout, retries)
    for error_indication, error_status, _, _ in setCmd(
        engine, usm, transport, ContextData(),
        ObjectType(ObjectIdentity(oid), type_map[value_type]),
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "oid": oid}
        if error_status:
            return {"error": str(error_status), "host": host, "oid": oid}
        return {"status": "ok", "host": host, "oid": oid, "value": value}
    return {"error": "No response", "host": host, "oid": oid}
```

> **pysnmp v7 import note:** If `pyasn1_modules.rfc1902` is unavailable, replace `Counter32`/`Gauge32` with `pyasn1.type.univ.Integer`. Verify available types with `python -c "from pysnmp.hlapi import *; help()"`.

- [ ] **Step 5: Run tests to confirm they pass**

```bash
uv run pytest tests/test_query.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/core/query.py tests/test_query.py tests/conftest.py
git commit -m "feat: add core query operations (get, getnext, walk, bulk, set)"
```

---

## Task 7: `core/trap.py` — Trap Send & Listen

**Files:**
- Create: `src/snmpv3_utils/core/trap.py`
- Create: `tests/test_trap.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trap.py
from unittest.mock import patch, MagicMock
import pytest
from snmpv3_utils.core.trap import send_trap


@pytest.fixture
def usm(usm_no_auth):
    return usm_no_auth


class TestSendTrap:
    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_trap_returns_ok(self, mock_send, usm):
        mock_send.return_value = iter([(None, None, None, [])])
        result = send_trap("192.168.1.1", usm, inform=False)
        assert result.get("status") == "ok"

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_inform_returns_ok(self, mock_send, usm):
        mock_send.return_value = iter([(None, None, None, [])])
        result = send_trap("192.168.1.1", usm, inform=True)
        assert result.get("status") == "ok"
        assert result.get("inform") is True

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_trap_returns_error_on_failure(self, mock_send, usm):
        mock_send.return_value = iter([("RequestTimedOut", None, None, [])])
        result = send_trap("192.168.1.1", usm, inform=False)
        assert "error" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_trap.py -v
```

- [ ] **Step 3: Write `core/trap.py`**

```python
# src/snmpv3_utils/core/trap.py
"""Trap send and receive operations.

send_trap: fire-and-forget (trap) or acknowledged (inform, --inform flag).
listen: blocking trap receiver for a single USM credential set.

Note on trap listener: pysnmp v7 uses asyncio for its notification receiver.
If the synchronous ntfrcv API is unavailable in your pysnmp version, use the
asyncio-based approach documented at https://pysnmp.readthedocs.io/
"""
from typing import Any, Callable

from pysnmp.hlapi import (
    ContextData,
    NotificationType,
    ObjectIdentity,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    sendNotification,
)


def send_trap(
    host: str,
    usm: UsmUserData,
    inform: bool = False,
    port: int = 162,
    timeout: int = 5,
    retries: int = 3,
    oid: str = "1.3.6.1.6.3.1.1.5.1",  # coldStart
) -> dict[str, Any]:
    """Send an SNMPv3 trap or inform.

    inform=False: fire-and-forget (no acknowledgment expected).
    inform=True:  INFORM-REQUEST — waits for acknowledgment from receiver.
    """
    engine = SnmpEngine()
    transport = UdpTransportTarget((host, port), timeout=timeout, retries=retries)
    notification_type = "inform" if inform else "trap"

    for error_indication, error_status, _, _ in sendNotification(
        engine,
        usm,
        transport,
        ContextData(),
        notification_type,
        NotificationType(ObjectIdentity(oid)),
    ):
        if error_indication:
            return {"error": str(error_indication), "host": host, "type": notification_type}
        if error_status:
            return {"error": str(error_status), "host": host, "type": notification_type}
        return {"status": "ok", "host": host, "type": notification_type, "inform": inform}

    return {"error": "No response", "host": host}


def listen(
    port: int,
    usm: UsmUserData,
    on_trap: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Block and receive incoming SNMPv3 traps, calling on_trap for each one.

    v1 limitation: single USM credential set per invocation.

    This function requires pysnmp's notification receiver infrastructure.
    Refer to https://pysnmp.readthedocs.io/en/latest/examples/v3arch/asyncio/
    for the asyncio-based implementation required by pysnmp v7.

    on_trap: called with a dict {"host": ..., "oid": ..., "value": ...} per received var-bind.
             If None, traps are printed to stdout.
    """
    # pysnmp v7 asyncio-based trap listener
    # Implementation note: pysnmp v7 removed the synchronous asyncore dispatcher.
    # Use asyncio.run() with the v3arch asyncio ntfrcv module.
    # See: pysnmp.entity.rfc3413.asyncio.ntfrcv (verify module path for your version)
    raise NotImplementedError(
        "Trap listener requires pysnmp v7 asyncio integration. "
        "See docs/superpowers/specs/2026-03-20-snmpv3-utils-design.md for context, "
        "and pysnmp docs for asyncio ntfrcv implementation."
    )
```

> **Implementation note for `listen`:** pysnmp v7 removed the old `asyncore`-based dispatcher.
> The trap listener must be implemented using `asyncio`. Check the pysnmp lextudio docs/examples
> for the correct v7 asyncio notification receiver API before implementing. The `NotImplementedError`
> is intentional — it marks this as a known stub to complete.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_trap.py -v
```

Expected: `TestSendTrap` tests pass. `listen` is not tested (it's a stub).

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/trap.py tests/test_trap.py
git commit -m "feat: add core trap send (trap/inform); listen stub pending asyncio impl"
```

---

## Task 8: `core/auth.py` — Credential Testing

**Files:**
- Create: `src/snmpv3_utils/core/auth.py`
- Create: `tests/test_auth.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
import csv
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from snmpv3_utils.core.auth import check_creds, bulk_check
from snmpv3_utils.security import Credentials, SecurityLevel


@pytest.fixture
def usm(usm_no_auth):
    return usm_no_auth


class TestCheckCreds:
    @patch("snmpv3_utils.core.auth.get")
    def test_success_when_get_returns_value(self, mock_get, usm):
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        result = check_creds("192.168.1.1", usm)
        assert result["status"] == "ok"
        assert result["host"] == "192.168.1.1"

    @patch("snmpv3_utils.core.auth.get")
    def test_failure_when_get_returns_error(self, mock_get, usm):
        mock_get.return_value = {"error": "wrongDigest"}
        result = check_creds("192.168.1.1", usm)
        assert result["status"] == "failed"
        assert "error" in result


class TestBulkCheck:
    def _make_csv(self, rows: list[dict]) -> Path:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=[
            "username", "auth_protocol", "auth_key",
            "priv_protocol", "priv_key", "security_level"
        ])
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @patch("snmpv3_utils.core.auth.check_creds")
    def test_bulk_returns_result_per_row(self, mock_check, tmp_path):
        mock_check.side_effect = [
            {"status": "ok", "host": "192.168.1.1", "username": "admin"},
            {"status": "failed", "host": "192.168.1.1", "username": "wrong"},
        ]
        csv_content = self._make_csv([
            {"username": "admin", "auth_protocol": "SHA256", "auth_key": "pass",
             "priv_protocol": "AES128", "priv_key": "priv", "security_level": "authPriv"},
            {"username": "wrong", "auth_protocol": "", "auth_key": "",
             "priv_protocol": "", "priv_key": "", "security_level": "noAuthNoPriv"},
        ])
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "failed"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 3: Write `core/auth.py`**

```python
# src/snmpv3_utils/core/auth.py
"""Credential verification operations.

check_creds: test a single USM credential set against a host.
bulk_check: test all rows from a CSV credential file against a single host.
"""
import csv
from pathlib import Path
from typing import Any

from pysnmp.hlapi import UsmUserData

from snmpv3_utils.core.query import get
from snmpv3_utils.security import (
    AuthProtocol,
    Credentials,
    PrivProtocol,
    SecurityLevel,
    build_usm_user,
)

_SYSDESCR_OID = "1.3.6.1.2.1.1.1.0"


def check_creds(
    host: str,
    usm: UsmUserData,
    port: int = 161,
    timeout: int = 5,
    retries: int = 1,
    username: str = "",
) -> dict[str, Any]:
    """Test credentials by performing a GET on sysDescr.

    Returns {"status": "ok", ...} or {"status": "failed", "error": ..., ...}.
    """
    result = get(host, _SYSDESCR_OID, usm, port=port, timeout=timeout, retries=retries)
    if "error" in result:
        return {"status": "failed", "host": host, "username": username, "error": result["error"]}
    return {"status": "ok", "host": host, "username": username, "sysdescr": result.get("value")}


def bulk_check(host: str, csv_path: Path) -> list[dict[str, Any]]:
    """Test every credential row in a CSV against a single host.

    CSV format: username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
    Returns a list of check_creds results, one per row.
    """
    results = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            creds = Credentials(
                username=row.get("username", ""),
                auth_protocol=AuthProtocol(row["auth_protocol"]) if row.get("auth_protocol") else None,
                auth_key=row.get("auth_key") or None,
                priv_protocol=PrivProtocol(row["priv_protocol"]) if row.get("priv_protocol") else None,
                priv_key=row.get("priv_key") or None,
                security_level=SecurityLevel(row.get("security_level", "noAuthNoPriv")),
            )
            try:
                usm = build_usm_user(creds)
            except ValueError as e:
                results.append({"status": "failed", "host": host, "username": creds.username, "error": str(e)})
                continue
            results.append(check_creds(host, usm, username=creds.username))
    return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/core/auth.py tests/test_auth.py
git commit -m "feat: add core auth operations (check_creds, bulk_check)"
```

---

## Task 9: CLI — `main.py` + `query.py`

**Files:**
- Create: `src/snmpv3_utils/cli/main.py`
- Create: `src/snmpv3_utils/cli/query.py`
- Modify: `tests/` — add CLI tests inline

- [ ] **Step 1: Write `cli/main.py`**

```python
# src/snmpv3_utils/cli/main.py
"""Root CLI application — registers all subcommand groups."""
import typer
from snmpv3_utils.cli import query, trap, auth, profile

app = typer.Typer(
    name="snmpv3",
    help="SNMPv3 testing utility — GET, WALK, SET, traps, credential testing.",
    no_args_is_help=True,
)

app.add_typer(query.app, name="query", help="SNMP query operations (get, getnext, walk, bulk, set).")
app.add_typer(trap.app, name="trap", help="Trap operations (send, listen).")
app.add_typer(auth.app, name="auth", help="Credential testing (check, bulk).")
app.add_typer(profile.app, name="profile", help="Manage credential profiles.")


if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Write stub `cli/trap.py`, `cli/auth.py`, `cli/profile.py`** (so `main.py` imports don't fail)

```python
# src/snmpv3_utils/cli/trap.py
import typer
app = typer.Typer(no_args_is_help=True)
```

```python
# src/snmpv3_utils/cli/auth.py
import typer
app = typer.Typer(no_args_is_help=True)
```

```python
# src/snmpv3_utils/cli/profile.py
import typer
app = typer.Typer(no_args_is_help=True)
```

- [ ] **Step 3: Write the failing tests for the query CLI**

```python
# tests/test_cli_query.py
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestQueryGet:
    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_get_outputs_json(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(app, [
            "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"
        ])
        assert result.exit_code == 0
        assert "Linux" in result.output

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_get_exits_nonzero_on_error(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"error": "Timeout"}

        result = runner.invoke(app, [
            "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"
        ])
        assert result.exit_code != 0


class TestQueryWalk:
    @patch("snmpv3_utils.cli.query.core_walk")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_walk_outputs_json_array(self, mock_usm, mock_creds, mock_walk):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_walk.return_value = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
        ]
        result = runner.invoke(app, [
            "query", "walk", "192.168.1.1", "1.3.6.1.2.1.1", "--format", "json"
        ])
        assert result.exit_code == 0
        assert "1.3.6.1.2.1.1.1.0" in result.output
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
uv run pytest tests/test_cli_query.py -v
```

- [ ] **Step 5: Write `cli/query.py`**

```python
# src/snmpv3_utils/cli/query.py
"""CLI commands for snmpv3 query *."""
from typing import Annotated, Optional

import typer

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.query import bulk as core_bulk
from snmpv3_utils.core.query import get as core_get
from snmpv3_utils.core.query import getnext as core_getnext
from snmpv3_utils.core.query import set_oid as core_set
from snmpv3_utils.core.query import walk as core_walk
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single
from snmpv3_utils.security import AuthProtocol, PrivProtocol, SecurityLevel, build_usm_user

app = typer.Typer(no_args_is_help=True)

# Reusable credential option annotations
_UsernameOpt = Annotated[Optional[str], typer.Option("--username", "-u", help="SNMPv3 username")]
_AuthProtoOpt = Annotated[Optional[AuthProtocol], typer.Option("--auth-protocol", help="Auth protocol")]
_AuthKeyOpt = Annotated[Optional[str], typer.Option("--auth-key", help="Auth passphrase")]
_PrivProtoOpt = Annotated[Optional[PrivProtocol], typer.Option("--priv-protocol", help="Priv protocol")]
_PrivKeyOpt = Annotated[Optional[str], typer.Option("--priv-key", help="Priv passphrase")]
_SecLevelOpt = Annotated[Optional[SecurityLevel], typer.Option("--security-level", help="Security level")]
_ProfileOpt = Annotated[Optional[str], typer.Option("--profile", "-p", help="Credential profile name")]
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f", help="Output format")]
_PortOpt = Annotated[Optional[int], typer.Option("--port", help="UDP port")]
_TimeoutOpt = Annotated[Optional[int], typer.Option("--timeout", help="Timeout seconds")]
_RetriesOpt = Annotated[Optional[int], typer.Option("--retries", help="Number of retries")]


def _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries):  # noqa: E501
    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
        "port": port, "timeout": timeout, "retries": retries,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    return build_usm_user(creds), creds


@app.command()
def get(
    host: str,
    oid: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Fetch a single OID value."""
    usm, creds = _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries)  # noqa: E501
    result = core_get(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def getnext(
    host: str,
    oid: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Return the next OID after the given one (single GETNEXT step)."""
    usm, creds = _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries)  # noqa: E501
    result = core_getnext(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def walk(
    host: str,
    oid: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Traverse the MIB subtree rooted at oid."""
    usm, creds = _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries)  # noqa: E501
    results = core_walk(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    print_records(results, fmt=fmt)


@app.command()
def bulk(
    host: str,
    oid: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    max_repetitions: Annotated[int, typer.Option("--max-repetitions", help="Max repetitions for GETBULK")] = 25,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """GETBULK retrieval of a MIB subtree."""
    usm, creds = _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries)  # noqa: E501
    results = core_bulk(host, oid, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries, max_repetitions=max_repetitions)  # noqa: E501
    print_records(results, fmt=fmt)


@app.command(name="set")
def set_cmd(
    host: str,
    oid: str,
    value: str,
    type_: Annotated[str, typer.Option("--type", help="Value type: int | str | hex")] = "str",
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Set an OID value. --type int|str|hex required."""
    usm, creds = _build_usm(profile, username, auth_protocol, auth_key, priv_protocol, priv_key, security_level, port, timeout, retries)  # noqa: E501
    result = core_set(host, oid, value, type_, usm, port=creds.port, timeout=creds.timeout, retries=creds.retries)
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
uv run pytest tests/test_cli_query.py -v
```

- [ ] **Step 7: Smoke test the CLI**

```bash
uv run snmpv3 --help
uv run snmpv3 query --help
uv run snmpv3 query get --help
```

Expected: help text for all three. No errors.

- [ ] **Step 8: Commit**

```bash
git add src/snmpv3_utils/cli/ tests/test_cli_query.py
git commit -m "feat: add CLI query commands (get, getnext, walk, bulk, set)"
```

---

## Task 10: CLI — `trap.py`

**Files:**
- Modify: `src/snmpv3_utils/cli/trap.py` (replace stub)
- Create: `tests/test_cli_trap.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_trap.py
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestTrapSend:
    @patch("snmpv3_utils.cli.trap.core_send_trap")
    @patch("snmpv3_utils.cli.trap.resolve_credentials")
    @patch("snmpv3_utils.cli.trap.build_usm_user")
    def test_send_returns_ok(self, mock_usm, mock_creds, mock_trap):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_trap.return_value = {"status": "ok", "host": "192.168.1.1", "type": "trap", "inform": False}

        result = runner.invoke(app, ["trap", "send", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 0
        assert "ok" in result.output

    @patch("snmpv3_utils.cli.trap.core_send_trap")
    @patch("snmpv3_utils.cli.trap.resolve_credentials")
    @patch("snmpv3_utils.cli.trap.build_usm_user")
    def test_send_inform_flag(self, mock_usm, mock_creds, mock_trap):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_trap.return_value = {"status": "ok", "host": "192.168.1.1", "type": "inform", "inform": True}

        result = runner.invoke(app, ["trap", "send", "192.168.1.1", "--inform", "--format", "json"])
        assert result.exit_code == 0
        _, kwargs = mock_trap.call_args
        assert kwargs.get("inform") is True or mock_trap.call_args[0][2] is True


class TestTrapListen:
    def test_listen_exits_nonzero_with_not_implemented_message(self):
        """The listen stub should exit 1 and print the NotImplementedError message."""
        result = runner.invoke(app, ["trap", "listen", "--port", "16200"])
        assert result.exit_code != 0
        assert "not implemented" in result.output.lower()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_cli_trap.py -v
```

Expected: `ImportError` or test failures — `cli/trap.py` is still a stub.

- [ ] **Step 3: Write `cli/trap.py`**

```python
# src/snmpv3_utils/cli/trap.py
"""CLI commands for snmpv3 trap *."""
from typing import Annotated, Optional

import typer

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.trap import send_trap as core_send_trap
from snmpv3_utils.output import OutputFormat, print_error, print_single
from snmpv3_utils.security import AuthProtocol, PrivProtocol, SecurityLevel, build_usm_user

app = typer.Typer(no_args_is_help=True)

_ProfileOpt = Annotated[Optional[str], typer.Option("--profile", "-p")]
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f")]
_UsernameOpt = Annotated[Optional[str], typer.Option("--username", "-u")]
_AuthProtoOpt = Annotated[Optional[AuthProtocol], typer.Option("--auth-protocol")]
_AuthKeyOpt = Annotated[Optional[str], typer.Option("--auth-key")]
_PrivProtoOpt = Annotated[Optional[PrivProtocol], typer.Option("--priv-protocol")]
_PrivKeyOpt = Annotated[Optional[str], typer.Option("--priv-key")]
_SecLevelOpt = Annotated[Optional[SecurityLevel], typer.Option("--security-level")]
_PortOpt = Annotated[Optional[int], typer.Option("--port")]
_TimeoutOpt = Annotated[Optional[int], typer.Option("--timeout")]
_RetriesOpt = Annotated[Optional[int], typer.Option("--retries")]


@app.command()
def send(
    host: str,
    oid: Annotated[str, typer.Option("--oid", help="Trap OID")] = "1.3.6.1.6.3.1.1.5.1",
    inform: Annotated[bool, typer.Option("--inform", help="Send INFORM-REQUEST (acknowledged)")] = False,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Send an SNMPv3 trap or inform to a host.

    By default sends a fire-and-forget trap (coldStart OID).
    Use --inform to send an INFORM-REQUEST and wait for acknowledgment.
    """
    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
        "port": port or 162, "timeout": timeout, "retries": retries,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)
    result = core_send_trap(host, usm, inform=inform, port=creds.port, timeout=creds.timeout, retries=creds.retries, oid=oid)  # noqa: E501
    if "error" in result:
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def listen(
    port: Annotated[int, typer.Option("--port", help="UDP port to listen on")] = 162,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Listen for incoming SNMPv3 traps (blocking).

    Decrypts traps using the provided or configured credentials.
    v1 limitation: single USM credential set per invocation.
    Press Ctrl+C to stop.
    """
    from snmpv3_utils.core.trap import listen as core_listen
    from snmpv3_utils.output import print_records

    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)

    typer.echo(f"Listening for SNMPv3 traps on port {port}... (Ctrl+C to stop)")
    try:
        core_listen(port, usm, on_trap=lambda r: print_single(r, fmt=fmt))
    except NotImplementedError as e:
        typer.echo(f"[not implemented] {e}", err=True)
        raise typer.Exit(1)
    except KeyboardInterrupt:
        typer.echo("\nStopped.")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_cli_trap.py -v
```

Expected: all tests pass including `test_listen_exits_nonzero_with_not_implemented_message`.

- [ ] **Step 5: Commit**

```bash
git add src/snmpv3_utils/cli/trap.py tests/test_cli_trap.py
git commit -m "feat: add CLI trap commands (send, listen)"
```

---

## Task 11: CLI — `auth.py` + `profile.py`

**Files:**
- Modify: `src/snmpv3_utils/cli/auth.py`
- Modify: `src/snmpv3_utils/cli/profile.py`
- Create: `tests/test_cli_auth.py`
- Create: `tests/test_cli_profile.py`

- [ ] **Step 1: Write the failing tests for auth and profile CLI**

```python
# tests/test_cli_auth.py
from pathlib import Path
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestAuthCheck:
    @patch("snmpv3_utils.cli.auth.core_check_creds")
    @patch("snmpv3_utils.cli.auth.resolve_credentials")
    @patch("snmpv3_utils.cli.auth.build_usm_user")
    def test_check_success(self, mock_usm, mock_creds, mock_check):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_check.return_value = {"status": "ok", "host": "192.168.1.1", "username": "admin"}
        result = runner.invoke(app, ["auth", "check", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.auth.core_check_creds")
    @patch("snmpv3_utils.cli.auth.resolve_credentials")
    @patch("snmpv3_utils.cli.auth.build_usm_user")
    def test_check_failure_exits_nonzero(self, mock_usm, mock_creds, mock_check):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_check.return_value = {"status": "failed", "host": "192.168.1.1", "error": "wrongDigest"}
        result = runner.invoke(app, ["auth", "check", "192.168.1.1", "--format", "json"])
        assert result.exit_code != 0
```

```python
# tests/test_cli_profile.py
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


def test_profile_add_and_list(tmp_path):
    with patch("snmpv3_utils.config.get_profiles_path", return_value=tmp_path / "profiles.toml"):
        result = runner.invoke(app, [
            "profile", "add", "testprofile",
            "--username", "admin",
            "--security-level", "noAuthNoPriv",
        ])
        assert result.exit_code == 0
        assert "saved" in result.output

        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0
        assert "testprofile" in result.output


def test_profile_delete(tmp_path):
    with patch("snmpv3_utils.config.get_profiles_path", return_value=tmp_path / "profiles.toml"):
        runner.invoke(app, ["profile", "add", "todelete", "--username", "x"])
        result = runner.invoke(app, ["profile", "delete", "todelete"])
        assert result.exit_code == 0
        assert "deleted" in result.output
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_cli_auth.py tests/test_cli_profile.py -v
```

Expected: `ImportError` or failures — `cli/auth.py` and `cli/profile.py` are still stubs.

- [ ] **Step 3: Write `cli/auth.py`**

```python
# src/snmpv3_utils/cli/auth.py
"""CLI commands for snmpv3 auth *."""
from pathlib import Path
from typing import Annotated, Optional

import typer

from snmpv3_utils.config import resolve_credentials
from snmpv3_utils.core.auth import bulk_check as core_bulk_check
from snmpv3_utils.core.auth import check_creds as core_check_creds
from snmpv3_utils.output import OutputFormat, print_error, print_records, print_single
from snmpv3_utils.security import AuthProtocol, PrivProtocol, SecurityLevel, build_usm_user

app = typer.Typer(no_args_is_help=True)

_ProfileOpt = Annotated[Optional[str], typer.Option("--profile", "-p")]
_FormatOpt = Annotated[OutputFormat, typer.Option("--format", "-f")]
_UsernameOpt = Annotated[Optional[str], typer.Option("--username", "-u")]
_AuthProtoOpt = Annotated[Optional[AuthProtocol], typer.Option("--auth-protocol")]
_AuthKeyOpt = Annotated[Optional[str], typer.Option("--auth-key")]
_PrivProtoOpt = Annotated[Optional[PrivProtocol], typer.Option("--priv-protocol")]
_PrivKeyOpt = Annotated[Optional[str], typer.Option("--priv-key")]
_SecLevelOpt = Annotated[Optional[SecurityLevel], typer.Option("--security-level")]
_PortOpt = Annotated[Optional[int], typer.Option("--port")]
_TimeoutOpt = Annotated[Optional[int], typer.Option("--timeout")]
_RetriesOpt = Annotated[Optional[int], typer.Option("--retries")]


@app.command()
def check(
    host: str,
    profile: _ProfileOpt = None,
    username: _UsernameOpt = None,
    auth_protocol: _AuthProtoOpt = None,
    auth_key: _AuthKeyOpt = None,
    priv_protocol: _PrivProtoOpt = None,
    priv_key: _PrivKeyOpt = None,
    security_level: _SecLevelOpt = None,
    port: _PortOpt = None,
    timeout: _TimeoutOpt = None,
    retries: _RetriesOpt = None,
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Test a single set of credentials against a host."""
    overrides = {
        "username": username, "auth_protocol": auth_protocol, "auth_key": auth_key,
        "priv_protocol": priv_protocol, "priv_key": priv_key, "security_level": security_level,
        "port": port, "timeout": timeout, "retries": retries,
    }
    creds = resolve_credentials(profile_name=profile, cli_overrides=overrides)
    usm = build_usm_user(creds)
    result = core_check_creds(host, usm, port=creds.port, timeout=creds.timeout, retries=1, username=creds.username)
    if result["status"] == "failed":
        print_error(result, fmt=fmt)
        raise typer.Exit(1)
    print_single(result, fmt=fmt)


@app.command()
def bulk(
    host: str,
    file: Annotated[Path, typer.Option("--file", "-f", help="CSV file with credentials")],
    fmt: _FormatOpt = OutputFormat.RICH,
) -> None:
    """Test all credential rows in a CSV file against a single host.

    CSV format: username,auth_protocol,auth_key,priv_protocol,priv_key,security_level
    """
    if not file.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(1)
    results = core_bulk_check(host, file)
    print_records(results, fmt=fmt)
```

- [ ] **Step 2: Write `cli/profile.py`**

```python
# src/snmpv3_utils/cli/profile.py
"""CLI commands for snmpv3 profile *."""
import json
from dataclasses import asdict
from typing import Annotated, Optional

import typer

from snmpv3_utils.config import delete_profile, list_profiles, load_profile, save_profile
from snmpv3_utils.output import OutputFormat
from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel

app = typer.Typer(no_args_is_help=True)


@app.command(name="list")
def list_cmd(
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.RICH,
) -> None:
    """List all saved profiles."""
    names = list_profiles()
    if not names:
        typer.echo("No profiles saved.")
        return
    if fmt == OutputFormat.JSON:
        print(json.dumps(names))
    else:
        for name in names:
            typer.echo(f"  {name}")


@app.command()
def show(
    name: str,
    fmt: Annotated[OutputFormat, typer.Option("--format", "-f")] = OutputFormat.RICH,
) -> None:
    """Show details for a named profile."""
    try:
        profile = load_profile(name)
    except KeyError:
        typer.echo(f"Profile '{name}' not found.", err=True)
        raise typer.Exit(1)
    data = {k: (v.value if hasattr(v, "value") else v) for k, v in asdict(profile).items()}
    if fmt == OutputFormat.JSON:
        print(json.dumps(data))
    else:
        for k, v in data.items():
            typer.echo(f"  {k}: {v}")


@app.command()
def add(
    name: str,
    username: Annotated[str, typer.Option("--username", "-u")] = "",
    auth_protocol: Annotated[Optional[AuthProtocol], typer.Option("--auth-protocol")] = None,
    auth_key: Annotated[Optional[str], typer.Option("--auth-key")] = None,
    priv_protocol: Annotated[Optional[PrivProtocol], typer.Option("--priv-protocol")] = None,
    priv_key: Annotated[Optional[str], typer.Option("--priv-key")] = None,
    security_level: Annotated[SecurityLevel, typer.Option("--security-level")] = SecurityLevel.NO_AUTH_NO_PRIV,
    port: Annotated[int, typer.Option("--port")] = 161,
    timeout: Annotated[int, typer.Option("--timeout")] = 5,
    retries: Annotated[int, typer.Option("--retries")] = 3,
) -> None:
    """Add or update a named profile."""
    profile = Credentials(
        username=username,
        auth_protocol=auth_protocol,
        auth_key=auth_key,
        priv_protocol=priv_protocol,
        priv_key=priv_key,
        security_level=security_level,
        port=port,
        timeout=timeout,
        retries=retries,
    )
    save_profile(name, profile)
    typer.echo(f"Profile '{name}' saved.")


@app.command()
def delete(name: str) -> None:
    """Delete a named profile."""
    delete_profile(name)
    typer.echo(f"Profile '{name}' deleted.")
```

- [ ] **Step 5: Run all tests to confirm they pass**

```bash
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Run ruff and mypy across the whole project**

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

Fix any issues before committing.

- [ ] **Step 6: Commit**

```bash
git add src/snmpv3_utils/cli/auth.py src/snmpv3_utils/cli/profile.py tests/test_cli_auth.py tests/test_cli_profile.py
git commit -m "feat: add CLI auth and profile commands"
```

---

## Task 12: CI/CD Workflows

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write `ci.yml`**

```yaml
# .github/workflows/ci.yml
name: ci

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Format check (ruff)
        run: uv run ruff format --check .

      - name: Type check (mypy)
        run: uv run mypy src/

      - name: Tests
        run: uv run pytest --tb=short
```

- [ ] **Step 2: Write `release.yml`**

```yaml
# .github/workflows/release.yml
name: release

on:
  push:
    tags:
      - "v*"

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # needed to create GitHub Release

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.11

      - name: Install dependencies
        run: uv sync --all-extras

      - name: Run full CI suite
        run: |
          uv run ruff check .
          uv run ruff format --check .
          uv run mypy src/
          uv run pytest --tb=short

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
        run: uv publish

      - name: Extract changelog entry for this tag
        id: changelog
        run: |
          # Extract the section matching the tag version from CHANGELOG.md
          TAG="${GITHUB_REF_NAME}"
          VERSION="${TAG#v}"
          BODY=$(awk "/^## \[${VERSION}\]/{found=1; next} found && /^## /{exit} found{print}" CHANGELOG.md)
          echo "body<<EOF" >> "$GITHUB_OUTPUT"
          echo "$BODY" >> "$GITHUB_OUTPUT"
          echo "EOF" >> "$GITHUB_OUTPUT"

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          body: ${{ steps.changelog.outputs.body }}
          files: dist/*
```

- [ ] **Step 3: Commit and push to trigger CI**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflows for CI and release"
git push origin main
```

- [ ] **Step 4: Verify CI passes on GitHub**

```bash
gh run list --limit 3
```

Expected: the latest workflow run shows ✓.

---

## Task 13: Documentation

**Files:**
- Create: `CLAUDE.md`
- Create: `CONTRIBUTING.md`
- Create: `CHANGELOG.md`
- Create: `README.md`

- [ ] **Step 1: Write `CLAUDE.md`**

```markdown
# CLAUDE.md

Project instructions for AI assistants working on snmpv3-utils.

## Setup

```bash
uv sync --all-extras
```

## Key Commands

| Task | Command |
|------|---------|
| Run tests | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Type check | `uv run mypy src/` |
| Run CLI | `uv run snmpv3 --help` |

## Architecture Rules

- **`cli/`** — thin Typer wrappers only. No SNMP logic, no direct pysnmp imports.
- **`core/`** — all SNMP operations. Returns `dict` or `list[dict]`. No CLI, no rich.
- **`security.py`** — the only file that imports pysnmp auth/priv constants.
- **`output.py`** — the only file that imports rich. Takes dicts, formats for display.

## Adding a New Operation

1. Write the failing test in `tests/test_<module>.py`
2. Implement in `core/<module>.py`
3. Add the CLI command in `cli/<module>.py`
4. Add a CLI test using typer's `CliRunner`
5. Open an issue, work in a branch, open a PR

## PR & Issue Workflow

- All work starts with a GitHub Issue
- Branch from `main`, name: `feat/<issue-number>-<short-description>`
- PRs require CI to pass (ruff, mypy, pytest)
- Conventional commits required: `feat:`, `fix:`, `docs:`, `chore:`, `test:`

## pysnmp v7 Notes

- Import from `pysnmp.hlapi` for sync operations
- Auth constants: `usmHMACMD5AuthProtocol`, `usmHMACSHAAuthProtocol`, `usmHMAC192SHA256AuthProtocol`, `usmHMAC384SHA512AuthProtocol`
- Priv constants: `usmDESPrivProtocol`, `usmAesCfb128Protocol`, `usmAesCfb256Protocol`
- Trap listener requires asyncio (v7 removed asyncore dispatcher) — see `core/trap.py`
```

- [ ] **Step 2: Write `CONTRIBUTING.md`**

```markdown
# Contributing to snmpv3-utils

Thank you for contributing! This guide covers everything you need to get started.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `brew install uv`)
- [GitHub CLI](https://cli.github.com/) (`gh`) for issue/PR management

## Dev Setup

```bash
git clone https://github.com/<your-username>/snmpv3-utils
cd snmpv3-utils
uv sync --all-extras
```

Verify everything works:
```bash
uv run pytest
uv run snmpv3 --help
```

## Workflow

1. **Find or create a GitHub Issue** for the work you want to do
2. **Branch:** `git checkout -b feat/<issue-number>-short-description`
3. **Write tests first** — we use TDD; tests live in `tests/`
4. **Implement** — keep `cli/` thin and business logic in `core/`
5. **Run checks locally** before pushing:
   ```bash
   uv run ruff check . && uv run ruff format . && uv run mypy src/ && uv run pytest
   ```
6. **Commit** using conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
7. **Open a PR** and reference the issue with `Closes #<number>`

## Adding a New SNMP Operation

1. Add the core function in `src/snmpv3_utils/core/<module>.py` — return `dict`/`list[dict]`
2. Add the CLI command in `src/snmpv3_utils/cli/<module>.py` — thin wrapper only
3. Write tests for both in `tests/`
4. Update `README.md` with usage example

## Code Style

- Formatter + linter: `ruff` (configured in `pyproject.toml`)
- Type checker: `mypy --strict`
- No classes unless clearly warranted — prefer functions
- Docstrings on all public functions (one-liner is fine if self-evident)
```

- [ ] **Step 3: Write `CHANGELOG.md`**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
```

- [ ] **Step 4: Write `README.md`**

```markdown
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
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md CONTRIBUTING.md CHANGELOG.md README.md
git commit -m "docs: add README, CONTRIBUTING, CLAUDE.md, CHANGELOG"
```

---

## Task 14: Issue & PR Templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `.github/ISSUE_TEMPLATE/feature_request.md`
- Create: `.github/ISSUE_TEMPLATE/new_operation.md`
- Create: `.github/pull_request_template.md`

- [ ] **Step 1: Write the templates**

```markdown
<!-- .github/ISSUE_TEMPLATE/bug_report.md -->
---
name: Bug report
about: Something is not working correctly
labels: bug
---

**Describe the bug**
A clear description of what is wrong.

**Command run**
```bash
snmpv3 ...
```

**Expected behavior**

**Actual behavior / error output**

**Environment**
- OS:
- Python version:
- snmpv3-utils version: (`snmpv3 --version`)
- pysnmp version:
```

```markdown
<!-- .github/ISSUE_TEMPLATE/feature_request.md -->
---
name: Feature request
about: Suggest an improvement or new capability
labels: enhancement
---

**What would you like to see?**

**Why is this useful?**

**Any implementation ideas?**
```

```markdown
<!-- .github/ISSUE_TEMPLATE/new_operation.md -->
---
name: New SNMP operation
about: Propose adding a new SNMP command
labels: enhancement, new-operation
---

**Operation name and description**

**Which group does it belong to?**
- [ ] query
- [ ] trap
- [ ] auth
- [ ] new group (describe below)

**Proposed command signature**
```bash
snmpv3 <group> <command> ...
```

**pysnmp API used**

**Any edge cases to handle?**
```

```markdown
<!-- .github/pull_request_template.md -->
## Summary

Closes #

## Changes

-

## Checklist

- [ ] Tests written before implementation (TDD)
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run mypy src/` passes
- [ ] `CHANGELOG.md` updated (if user-facing change)
- [ ] `README.md` updated (if new command or changed behavior)
```

- [ ] **Step 2: Commit**

```bash
git add .github/ISSUE_TEMPLATE/ .github/pull_request_template.md
git commit -m "chore: add GitHub issue and PR templates"
git push origin main
```

---

## Task 15: Final Verification

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -v --tb=short
```

Expected: all tests pass, no warnings.

- [ ] **Step 2: Run all quality checks**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
```

Expected: zero errors.

- [ ] **Step 3: Verify the CLI entry point works end to end**

```bash
uv run snmpv3 --help
uv run snmpv3 query --help
uv run snmpv3 trap --help
uv run snmpv3 auth --help
uv run snmpv3 profile --help
```

Expected: all help pages display correctly with correct command listings.

- [ ] **Step 4: Test profile management locally**

```bash
uv run snmpv3 profile add testprofile --username testuser --security-level noAuthNoPriv
uv run snmpv3 profile list
uv run snmpv3 profile show testprofile
uv run snmpv3 profile delete testprofile
uv run snmpv3 profile list
```

Expected: profile round-trip works.

- [ ] **Step 5: Build the package**

```bash
uv build
ls dist/
```

Expected: `dist/snmpv3_utils-0.1.0-py3-none-any.whl` and `.tar.gz` present.

- [ ] **Step 6: Test pip install from the built wheel**

```bash
pip install dist/snmpv3_utils-0.1.0-py3-none-any.whl --force-reinstall
snmpv3 --help
```

Expected: `snmpv3` command available and working.

- [ ] **Step 7: Push and confirm CI passes**

```bash
git push origin main
gh run list --limit 1
```

Expected: CI run shows ✓.

- [ ] **Step 8: Tag v0.1.0 and push (when ready to release)**

```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers `release.yml`. Before running, ensure `PYPI_TOKEN` is set in the repo's GitHub Secrets (`gh secret set PYPI_TOKEN`).

---

## Known Stubs / Follow-up Issues to Open After v0.1.0

After completing this plan, open the following GitHub Issues for follow-up work:

1. **`trap listen` asyncio implementation** — `core/trap.py:listen` raises `NotImplementedError`. Needs pysnmp v7 asyncio ntfrcv integration.
2. **`--version` flag** — add `typer` version callback to `cli/main.py`.
3. **Standalone executable** — investigate PyInstaller/Nuitka packaging for Windows/Linux/macOS.
4. **Interactive TUI mode** — MIB tree browser.
