import logging
import sys
from unittest.mock import patch

import snmpv3_utils.debug
from snmpv3_utils.debug import configure_logging


class TestConfigureLogging:
    def teardown_method(self):
        """Remove handlers added during tests."""
        logger = logging.getLogger("snmpv3_utils")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)
        snmpv3_utils.debug._pysnmp_debug_enabled = False

    def test_no_verbosity_sets_warning(self):
        configure_logging(0)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.WARNING

    def test_single_v_sets_info(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.INFO

    def test_double_v_sets_debug(self):
        configure_logging(2)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.level == logging.DEBUG

    def test_handler_writes_to_stderr(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert len(logger.handlers) == 1
        assert logger.handlers[0].stream is sys.stderr

    def test_idempotent_no_duplicate_handlers(self):
        configure_logging(1)
        configure_logging(2)
        logger = logging.getLogger("snmpv3_utils")
        assert len(logger.handlers) == 1

    def test_formatter_updates_on_reconfig(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert "%(name)s" not in logger.handlers[0].formatter._fmt
        configure_logging(2)
        assert "%(name)s" in logger.handlers[0].formatter._fmt

    def test_vv_enables_pysnmp_debug(self):
        with patch("pysnmp.debug.set_logger") as mock_set:
            configure_logging(2)
            mock_set.assert_called_once()

    def test_propagate_disabled(self):
        configure_logging(1)
        logger = logging.getLogger("snmpv3_utils")
        assert logger.propagate is False
