# tests/test_trap.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from snmpv3_utils.core.trap import send_trap, stress_trap


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


class TestStressTrap:
    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_count_mode_sends_correct_number(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["sent"] == 10
        assert result["errors"] == 0
        assert result["host"] == "192.168.1.1"
        assert mock_send.call_count == 10

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_error_counting(self, mock_send, mock_transport):
        side_effects = [(None, None, None, [])] * 7 + [("timeout", None, None, [])] * 3
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["sent"] == 10
        assert result["errors"] == 3

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_success_rate_calculation(self, mock_send, mock_transport):
        side_effects = [(None, None, None, [])] * 8 + [("err", None, None, [])] * 2
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0)
        assert result["success_rate"] == "80.0%"

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_error_samples_dedup_keeps_first_five(self, mock_send, mock_transport):
        side_effects = [(f"error_{i}", None, None, []) for i in range(8)]
        mock_send.side_effect = side_effects
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=8, rate=0)
        assert len(result["error_samples"]) == 5
        assert result["error_samples"] == ["error_0", "error_1", "error_2", "error_3", "error_4"]

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_zero_count_no_division_error(self, mock_send, mock_transport):
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=0, rate=0)
        assert result["sent"] == 0
        assert result["success_rate"] == "N/A"
        assert result["rate_achieved"] == 0.0
        mock_send.assert_not_called()

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_result_shape(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=1, rate=0)
        expected_keys = {
            "host", "sent", "errors", "success_rate", "duration_s", "rate_achieved", "error_samples"
        }
        assert set(result.keys()) == expected_keys

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_on_progress_callback_called(self, mock_send, mock_transport):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        progress_calls = []
        stress_trap(
            "192.168.1.1", usm=MagicMock(), count=5, rate=0,
            on_progress=lambda dispatched, total: progress_calls.append((dispatched, total)),
        )
        assert len(progress_calls) == 5
        assert progress_calls[0] == (1, 5)
        assert progress_calls[-1] == (5, 5)

    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_concurrency_limits_inflight(self, mock_send, mock_transport):
        """Verify semaphore limits concurrent in-flight sends."""
        max_concurrent_seen = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        original_return = (None, None, None, [])

        async def _slow_send(*args, **kwargs):
            nonlocal max_concurrent_seen, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent_seen:
                    max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return original_return

        mock_send.side_effect = _slow_send
        mock_transport.create = AsyncMock(return_value=MagicMock())
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=10, rate=0, concurrency=3)
        assert result["sent"] == 10
        assert max_concurrent_seen <= 3

    @patch("snmpv3_utils.core.trap.time")
    @patch("snmpv3_utils.core.trap.UdpTransportTarget", autospec=True)
    @patch("snmpv3_utils.core.trap._async_send_notification", new_callable=AsyncMock)
    def test_duration_mode_stops_after_elapsed(self, mock_send, mock_transport, mock_time):
        mock_send.return_value = (None, None, None, [])
        mock_transport.create = AsyncMock(return_value=MagicMock())
        # Calls: start=0.0, loop check=0.0 (dispatch 1), loop check=0.5 (dispatch 2),
        # loop check=1.5 (stop), elapsed=1.5
        mock_time.monotonic.side_effect = [0.0, 0.0, 0.5, 1.5, 1.5]
        result = stress_trap("192.168.1.1", usm=MagicMock(), count=1000, duration=1, rate=0)
        assert result["sent"] == 2
