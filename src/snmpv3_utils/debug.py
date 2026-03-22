"""Verbose/debug output and SNMP error translation.

This module owns logging configuration, the USM report OID hint map,
and error translation. It is the only module that knows about verbosity
levels and error hint logic.
"""

from __future__ import annotations

import logging
import sys

from pysnmp.debug import Debug, set_logger

_LOGGER_NAME = "snmpv3_utils"


def configure_logging(verbosity: int) -> None:
    """Configure the snmpv3_utils root logger based on verbosity level.

    0 = WARNING (default), 1 = INFO (-v), 2 = DEBUG (-vv).
    Idempotent — safe to call multiple times.
    """
    logger = logging.getLogger(_LOGGER_NAME)

    level_map = {0: logging.WARNING, 1: logging.INFO}
    logger.setLevel(level_map.get(verbosity, logging.DEBUG))

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if verbosity >= 2:
            fmt = "%(levelname)s [%(name)s]: %(message)s"
        else:
            fmt = "%(levelname)s: %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)

    if verbosity >= 2:
        set_logger(Debug("all"))
