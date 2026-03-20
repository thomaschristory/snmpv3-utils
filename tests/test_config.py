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


def test_profile_port_overrides_env_port(tmp_path, monkeypatch):
    """Profile with default port should still override a non-default env port."""
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")
    monkeypatch.setenv("SNMPV3_PORT", "1234")

    # Profile explicitly saves port=161
    save_profile("myprofile", Credentials(username="admin", port=161))
    creds = resolve_credentials(profile_name="myprofile")
    assert creds.port == 161  # profile value wins over env


def test_profile_security_level_overrides_env(tmp_path, monkeypatch):
    """Profile with noAuthNoPriv should override env authPriv."""
    monkeypatch.setattr("snmpv3_utils.config.get_profiles_path", lambda: tmp_path / "profiles.toml")
    monkeypatch.setenv("SNMPV3_SECURITY_LEVEL", "authPriv")
    monkeypatch.setenv("SNMPV3_AUTH_KEY", "somekey")

    save_profile("minimal", Credentials(username="guest", security_level=SecurityLevel.NO_AUTH_NO_PRIV))
    creds = resolve_credentials(profile_name="minimal")
    assert creds.security_level == SecurityLevel.NO_AUTH_NO_PRIV  # profile wins
