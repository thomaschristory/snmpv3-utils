# src/snmpv3_utils/config.py
"""Credential resolution and profile management.

Resolution order (lowest to highest priority):
  built-in defaults -> env vars / .env file -> named profile -> CLI flags
"""

import os
import tomllib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from platformdirs import user_config_dir

from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel


def get_profiles_path() -> Path:
    """Return the platform-appropriate path for profiles.toml."""
    return Path(user_config_dir("snmpv3utils")) / "profiles.toml"


def load_from_env(default_port: int = 161) -> Credentials:
    """Read SNMPV3_* environment variables (and .env file) into a Credentials object."""
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
        port=int(os.getenv("SNMPV3_PORT", str(default_port))),
        timeout=int(os.getenv("SNMPV3_TIMEOUT", "5")),
        retries=int(os.getenv("SNMPV3_RETRIES", "3")),
    )


def load_profile_dict(name: str) -> dict[str, Any]:
    """Load profile as a sparse dict of only the fields present in TOML.

    Raises KeyError if not found.
    """
    path = get_profiles_path()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise KeyError(name) from None
    profiles = data.get("profiles", {})
    if name not in profiles:
        raise KeyError(name)
    result: dict[str, Any] = profiles[name]
    return result  # raw dict, only explicitly saved fields


def load_profile(name: str) -> Credentials:
    """Load a named profile as a Credentials object. Raises KeyError if not found."""
    p = load_profile_dict(name)
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
    import tomli_w

    path = get_profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    try:
        with open(path, "rb") as f:
            existing = tomllib.load(f)
    except FileNotFoundError:
        pass

    existing.setdefault("profiles", {})
    existing["profiles"][name] = {
        fname: (v.value if hasattr(v, "value") else v)
        for fname, v in asdict(creds).items()
        if v is not None
    }

    with open(path, "wb") as f:
        tomli_w.dump(existing, f)


def list_profiles() -> list[str]:
    """Return all profile names, or an empty list if no profiles file exists."""
    path = get_profiles_path()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return []
    return list(data.get("profiles", {}).keys())


def delete_profile(name: str) -> None:
    """Remove a profile. Raises KeyError if the profile doesn't exist."""
    import tomli_w

    path = get_profiles_path()
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise KeyError(name) from None
    profiles = data.get("profiles", {})
    if name not in profiles:
        raise KeyError(name)
    profiles.pop(name)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)


def _apply_overrides(base: Credentials, overrides: dict[str, Any]) -> Credentials:
    """Apply a sparse dict of overrides onto base Credentials.

    Only keys present in overrides are changed.
    """
    result_dict = asdict(base)
    for key, value in overrides.items():
        if key in result_dict:
            # Convert string enum values back to enum types
            if key == "auth_protocol" and value is not None:
                value = AuthProtocol(value) if isinstance(value, str) else value
            elif key == "priv_protocol" and value is not None:
                value = PrivProtocol(value) if isinstance(value, str) else value
            elif key == "security_level" and value is not None:
                value = SecurityLevel(value) if isinstance(value, str) else value
            result_dict[key] = value
    return Credentials(**result_dict)


def resolve_credentials(
    profile_name: str | None = None,
    cli_overrides: dict[str, Any] | None = None,
    default_port: int = 161,
) -> Credentials:
    """Merge credentials: defaults -> env -> profile -> CLI flags."""
    base = load_from_env(default_port=default_port)

    if profile_name:
        profile_dict = load_profile_dict(profile_name)  # sparse dict
        base = _apply_overrides(base, profile_dict)

    if cli_overrides:
        # Filter None values — CLI only passes what the user explicitly typed
        base = _apply_overrides(base, {k: v for k, v in cli_overrides.items() if v is not None})

    return base
