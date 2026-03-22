import logging

from snmpv3_utils.debug import configure_logging


class TestConfigureLogging:
    def teardown_method(self):
        """Remove handlers added during tests."""
        logger = logging.getLogger("snmpv3_utils")
        logger.handlers.clear()
        logger.setLevel(logging.WARNING)

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
        import sys
        assert logger.handlers[0].stream is sys.stderr

    def test_idempotent_no_duplicate_handlers(self):
        configure_logging(1)
        configure_logging(2)
        logger = logging.getLogger("snmpv3_utils")
        assert len(logger.handlers) == 1

    def test_vv_enables_pysnmp_debug(self):
        from unittest.mock import patch

        with patch("snmpv3_utils.debug.set_logger") as mock_set:
            configure_logging(2)
            mock_set.assert_called_once()
