# tests/test_query.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from snmpv3_utils.core.query import bulk, get, getnext, set_oid, walk


@pytest.fixture
def usm(usm_no_auth):
    return usm_no_auth


def _mock_cmd_result(oid="1.3.6.1.2.1.1.1.0", value="Linux router"):
    """Return a single (errorIndication, errorStatus, errorIndex, varBinds) tuple."""
    var_bind = MagicMock()
    var_bind.__getitem__ = MagicMock(
        side_effect=lambda i: MagicMock(
            prettyPrint=MagicMock(return_value=oid if i == 0 else value)
        )
    )
    return [(None, None, None, [var_bind])]


class TestGet:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._get_cmd_async", new_callable=AsyncMock)
    def test_returns_dict_with_oid_and_value(self, mock_get, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_get.return_value = _mock_cmd_result()[0]
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert "value" in result
        assert set(result.keys()) == {"oid", "value"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._get_cmd_async", new_callable=AsyncMock)
    def test_returns_error_dict_on_failure(self, mock_get, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_get.return_value = ("Timeout", None, None, [])
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    def test_returns_error_on_transport_failure(self, mock_transport, usm):
        mock_transport.side_effect = OSError("Connection refused")
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result
        assert "Connection refused" in result["error"]
        assert set(result.keys()) == {"error", "host", "oid"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._get_cmd_async", new_callable=AsyncMock)
    def test_returns_error_on_exception(self, mock_get, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_get.side_effect = RuntimeError("socket closed")
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result
        assert "socket closed" in result["error"]


class TestGetnext:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._next_cmd_async", new_callable=AsyncMock)
    def test_returns_dict_with_next_oid(self, mock_next, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_next.return_value = _mock_cmd_result(oid="1.3.6.1.2.1.1.2.0")[0]
        result = getnext("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert set(result.keys()) == {"oid", "value"}


class TestWalk:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._walk_cmd_async")
    def test_returns_list_of_dicts(self, mock_walk, mock_transport, usm):
        mock_transport.return_value = MagicMock()

        async def _async_gen(*args, **kwargs):
            yield (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.1.0", "Linux")[0][3])
            yield (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.2.0", "sysObjectID")[0][3])

        mock_walk.return_value = _async_gen()
        results = walk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._walk_cmd_async")
    def test_empty_walk_returns_empty_list(self, mock_walk, mock_transport, usm):
        mock_transport.return_value = MagicMock()

        async def _async_gen(*args, **kwargs):
            return
            yield  # make it an async generator

        mock_walk.return_value = _async_gen()
        results = walk("192.168.1.1", "1.3.6.1.2.1.99", usm)
        assert results == []


class TestBulk:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._bulk_cmd_async", new_callable=AsyncMock)
    def test_returns_list_of_dicts(self, mock_bulk, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_bulk.return_value = _mock_cmd_result()[0]
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._bulk_cmd_async", new_callable=AsyncMock)
    def test_returns_error_on_failure(self, mock_bulk, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_bulk.return_value = ("Timeout", None, None, [])
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert len(results) == 1
        assert "error" in results[0]
        assert set(results[0].keys()) == {"error", "host", "oid"}


class TestSet:
    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._set_cmd_async", new_callable=AsyncMock)
    def test_returns_success_dict(self, mock_set, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_set.return_value = (None, None, None, [])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "myrouter", "str", usm)
        assert result.get("status") == "ok"
        assert set(result.keys()) == {"status", "host", "oid", "value"}

    @patch("snmpv3_utils.core.query.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.query._set_cmd_async", new_callable=AsyncMock)
    def test_returns_error_on_failure(self, mock_set, mock_transport, usm):
        mock_transport.return_value = MagicMock()
        mock_set.return_value = ("noSuchObject", None, None, [])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "x", "str", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}

    def test_set_returns_error_with_host_on_invalid_type(self, usm):
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.1.0", "val", "bogus", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}
