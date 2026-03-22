"""Verbose/debug output and SNMP error translation.

This module owns logging configuration, the USM report OID hint map,
and error translation. It is the only module that knows about verbosity
levels and error hint logic.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snmpv3_utils.security import Credentials

_LOGGER_NAME = "snmpv3_utils"
_pysnmp_debug_enabled = False

USM_REPORT_HINTS: dict[str, str] = {
    "1.3.6.1.6.3.15.1.1.1.0": (
        "Agent does not support the requested security level"
    ),
    "1.3.6.1.6.3.15.1.1.2.0": (
        "Request outside agent's time window — possible clock skew or stale engine data"
    ),
    "1.3.6.1.6.3.15.1.1.3.0": "User not found on agent",
    "1.3.6.1.6.3.15.1.1.4.0": (
        "Engine ID mismatch — possible stale discovery"
    ),
    "1.3.6.1.6.3.15.1.1.5.0": (
        "Auth digest mismatch — verify auth protocol and key match agent config"
    ),
    "1.3.6.1.6.3.15.1.1.6.0": (
        "Decryption failed — verify priv protocol and key match agent config"
    ),
}

_ERROR_STRING_MAP: dict[str, str] = {
    "Wrong SNMP PDU digest": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.5.0"],
    "Unknown SNMP security name": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.3.0"],
    "Unsupported SNMP security level": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.1.0"],
    "Wrong SNMP PDU encoding": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.6.0"],
    "SNMP message is not in time window": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.2.0"],
    "Unknown SNMP engine ID": USM_REPORT_HINTS["1.3.6.1.6.3.15.1.1.4.0"],
}


def translate_error(error_str: str, creds: Credentials | None = None) -> str:
    """Enrich a pysnmp error string with a human-readable hint.

    If the error matches a known USM report, appends an actionable hint.
    At INFO level with creds provided, also shows what credentials were used.
    Unknown errors pass through unchanged.
    """
    hint = _ERROR_STRING_MAP.get(error_str)
    if hint is None:
        return error_str

    parts = [error_str, f" — {hint}"]

    logger = logging.getLogger(_LOGGER_NAME)
    if creds is not None and logger.isEnabledFor(logging.INFO):
        cred_parts = [f"user='{creds.username}'"]
        if creds.auth_protocol:
            cred_parts.append(f"auth={creds.auth_protocol.value}")
        if creds.priv_protocol:
            cred_parts.append(f"priv={creds.priv_protocol.value}")
        parts.append(f" (You used: {', '.join(cred_parts)})")

    return "".join(parts)


def configure_logging(verbosity: int) -> None:
    """Configure the snmpv3_utils root logger based on verbosity level.

    0 = WARNING (default), 1 = INFO (-v), 2 = DEBUG (-vv).
    Idempotent — safe to call multiple times.
    """
    global _pysnmp_debug_enabled  # noqa: PLW0603
    logger = logging.getLogger(_LOGGER_NAME)
    logger.propagate = False

    level_map = {0: logging.WARNING, 1: logging.INFO}
    logger.setLevel(level_map.get(verbosity, logging.DEBUG))

    if verbosity >= 2:
        fmt = "%(levelname)s [%(name)s]: %(message)s"
    else:
        fmt = "%(levelname)s: %(message)s"

    if not logger.handlers:
        logger.addHandler(logging.StreamHandler(sys.stderr))
    logger.handlers[0].setFormatter(logging.Formatter(fmt))

    if verbosity >= 2 and not _pysnmp_debug_enabled:
        from pysnmp.debug import Debug, set_logger

        set_logger(Debug("all"))
        _pysnmp_debug_enabled = True
