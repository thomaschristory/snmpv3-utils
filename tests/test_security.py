# tests/test_security.py
import pytest
from pysnmp.hlapi.v3arch.asyncio import UsmUserData
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


def test_auth_no_priv_missing_auth_key_raises():
    """authNoPriv requires auth_key to be set."""
    creds = Credentials(
        username="bad",
        auth_protocol=AuthProtocol.SHA256,
        # auth_key intentionally missing
        security_level=SecurityLevel.AUTH_NO_PRIV,
    )
    with pytest.raises(ValueError, match="auth_protocol and auth_key are required"):
        build_usm_user(creds)


def test_invalid_auth_priv_combination_raises():
    """authPriv requires both auth_key and priv_key."""
    creds = Credentials(
        username="bad",
        security_level=SecurityLevel.AUTH_PRIV,
    )
    with pytest.raises(ValueError, match="auth_protocol and auth_key are required"):
        build_usm_user(creds)
