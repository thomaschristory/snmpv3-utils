import logging
import sys
from unittest.mock import patch

import snmpv3_utils.debug
from snmpv3_utils.debug import USM_REPORT_HINTS, configure_logging, translate_error
from snmpv3_utils.security import AuthProtocol, Credentials, PrivProtocol, SecurityLevel


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


class TestUsmReportHints:
    def test_contains_all_six_usm_oids(self):
        expected_oids = [
            "1.3.6.1.6.3.15.1.1.1.0",
            "1.3.6.1.6.3.15.1.1.2.0",
            "1.3.6.1.6.3.15.1.1.3.0",
            "1.3.6.1.6.3.15.1.1.4.0",
            "1.3.6.1.6.3.15.1.1.5.0",
            "1.3.6.1.6.3.15.1.1.6.0",
        ]
        for oid in expected_oids:
            assert oid in USM_REPORT_HINTS


class TestTranslateError:
    def test_known_error_appends_hint(self):
        result = translate_error("Wrong SNMP PDU digest")
        assert "Wrong SNMP PDU digest" in result
        assert "auth protocol and key" in result.lower()

    def test_unknown_error_passes_through(self):
        result = translate_error("Some random error")
        assert result == "Some random error"

    def test_includes_creds_at_info_level(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.INFO)
        try:
            creds = Credentials(
                username="thomas",
                auth_protocol=AuthProtocol.SHA256,
                auth_key="testkey123",
                priv_protocol=PrivProtocol.AES128,
                priv_key="testkey123",
                security_level=SecurityLevel.AUTH_PRIV,
            )
            result = translate_error("Wrong SNMP PDU digest", creds=creds)
            assert "thomas" in result
            assert "SHA256" in result
            assert "AES128" in result
        finally:
            logger.setLevel(logging.WARNING)

    def test_skips_creds_when_none(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.INFO)
        try:
            result = translate_error("Wrong SNMP PDU digest", creds=None)
            assert "auth protocol and key" in result.lower()
            assert "You used" not in result
        finally:
            logger.setLevel(logging.WARNING)

    def test_skips_creds_below_info(self):
        import logging

        logger = logging.getLogger("snmpv3_utils")
        logger.setLevel(logging.WARNING)
        creds = Credentials(
            username="thomas",
            auth_protocol=AuthProtocol.SHA256,
            auth_key="testkey123",
            security_level=SecurityLevel.AUTH_NO_PRIV,
        )
        result = translate_error("Wrong SNMP PDU digest", creds=creds)
        assert "thomas" not in result
