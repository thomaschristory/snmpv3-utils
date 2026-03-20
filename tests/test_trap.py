# tests/test_trap.py
from unittest.mock import patch

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

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_trap_returns_error_on_no_response(self, mock_send, usm):
        mock_send.return_value = iter([])
        result = send_trap("192.168.1.1", usm, inform=False)
        assert "error" in result
        assert result.get("type") == "trap"
