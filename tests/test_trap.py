# tests/test_trap.py
import asyncio
from unittest.mock import AsyncMock, patch

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
        assert set(result.keys()) == {"status", "host", "type", "inform"}

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_inform_returns_ok(self, mock_send, usm):
        mock_send.return_value = iter([(None, None, None, [])])
        result = send_trap("192.168.1.1", usm, inform=True)
        assert result.get("status") == "ok"
        assert result.get("inform") is True
        assert set(result.keys()) == {"status", "host", "type", "inform"}

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_trap_returns_error_on_failure(self, mock_send, usm):
        mock_send.return_value = iter([("RequestTimedOut", None, None, [])])
        result = send_trap("192.168.1.1", usm, inform=False)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "type", "inform"}

    @patch("snmpv3_utils.core.trap.sendNotification")
    def test_send_trap_returns_error_on_no_response(self, mock_send, usm):
        mock_send.return_value = iter([])
        result = send_trap("192.168.1.1", usm, inform=False)
        assert "error" in result
        assert result.get("type") == "trap"
        assert result.get("inform") is False
        assert set(result.keys()) == {"error", "host", "type", "inform"}


class TestSendOne:
    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_none_on_success(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, None, None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result is None
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_error_indication(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = ("RequestTimedOut", None, None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result == "RequestTimedOut"

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_returns_error_status(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, "genErr", None, [])
        sem = asyncio.Semaphore(10)
        result = await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=False, sem=sem,
        )
        assert result == "genErr"

    @pytest.mark.asyncio
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    async def test_send_one_passes_inform_type(self, mock_send):
        from snmpv3_utils.core.trap import _send_one

        mock_send.return_value = (None, None, None, [])
        sem = asyncio.Semaphore(10)
        await _send_one(
            engine=object(), usm=object(), transport=object(),
            oid="1.3.6.1.6.3.1.1.5.1", inform=True, sem=sem,
        )
        call_args = mock_send.call_args
        assert call_args[0][4] == "inform"
