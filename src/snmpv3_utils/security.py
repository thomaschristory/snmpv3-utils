# src/snmpv3_utils/security.py
"""SNMPv3 USM parameter builder.

This is the only module in snmpv3_utils that imports pysnmp auth/priv protocol
constants. All other modules receive a pre-built UsmUserData object.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from pysnmp.hlapi.v3arch.asyncio import (
    UsmUserData as UsmUserData,
)
from pysnmp.hlapi.v3arch.asyncio import (
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
    security_level: SecurityLevel = field(default=SecurityLevel.NO_AUTH_NO_PRIV)
    port: int = 161
    timeout: int = 5
    retries: int = 3


def build_usm_user(creds: Credentials) -> UsmUserData:
    """Build a pysnmp UsmUserData from a Credentials object.

    Keys are encoded to bytes so that UsmUserData stores them as bytes,
    which allows callers to compare usm.authKey == b"..." and usm.privKey == b"...".

    Raises ValueError if the security_level requires fields that are missing.
    """
    level = creds.security_level

    if not creds.username:
        raise ValueError(
            "username is required. Provide --username, set SNMPV3_USERNAME,"
            " or use a profile (--profile)."
        )

    if level == SecurityLevel.NO_AUTH_NO_PRIV:
        return UsmUserData(
            creds.username,
            authProtocol=usmNoAuthProtocol,
            privProtocol=usmNoPrivProtocol,
        )

    if level in (SecurityLevel.AUTH_NO_PRIV, SecurityLevel.AUTH_PRIV):
        if not creds.auth_protocol or not creds.auth_key:
            raise ValueError(
                "auth_protocol and auth_key are required for authNoPriv and authPriv security levels"  # noqa: E501
            )
        if len(creds.auth_key) < 8:
            raise ValueError("auth_key must be at least 8 characters (RFC 3414)")

    auth_proto = creds.auth_protocol
    assert auth_proto is not None

    if level == SecurityLevel.AUTH_NO_PRIV:
        return UsmUserData(
            creds.username,
            authKey=creds.auth_key.encode() if isinstance(creds.auth_key, str) else creds.auth_key,
            authProtocol=_AUTH_PROTOCOL_MAP[auth_proto],
            privProtocol=usmNoPrivProtocol,
        )

    # AUTH_PRIV
    if not creds.priv_protocol or not creds.priv_key:
        raise ValueError("priv_protocol and priv_key are required for authPriv security level")
    if len(creds.priv_key) < 8:
        raise ValueError("priv_key must be at least 8 characters (RFC 3414)")

    return UsmUserData(
        creds.username,
        authKey=creds.auth_key.encode() if isinstance(creds.auth_key, str) else creds.auth_key,
        authProtocol=_AUTH_PROTOCOL_MAP[auth_proto],
        privKey=creds.priv_key.encode() if isinstance(creds.priv_key, str) else creds.priv_key,
        privProtocol=_PRIV_PROTOCOL_MAP[creds.priv_protocol],
    )
