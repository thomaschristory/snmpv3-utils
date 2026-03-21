# tests/test_query.py
from unittest.mock import MagicMock, patch

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
    @patch("snmpv3_utils.core.query.getCmd")
    def test_returns_dict_with_oid_and_value(self, mock_get, usm):
        mock_get.return_value = iter(_mock_cmd_result())
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert "value" in result
        assert set(result.keys()) == {"oid", "value"}

    @patch("snmpv3_utils.core.query.getCmd")
    def test_returns_error_dict_on_failure(self, mock_get, usm):
        mock_get.return_value = iter([("Timeout", None, None, [])])
        result = get("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}


class TestGetnext:
    @patch("snmpv3_utils.core.query.nextCmd")
    def test_returns_dict_with_next_oid(self, mock_next, usm):
        mock_next.return_value = iter(_mock_cmd_result(oid="1.3.6.1.2.1.1.2.0"))
        result = getnext("192.168.1.1", "1.3.6.1.2.1.1.1.0", usm)
        assert isinstance(result, dict)
        assert "oid" in result
        assert set(result.keys()) == {"oid", "value"}


class TestWalk:
    @patch("snmpv3_utils.core.query.walkCmd")
    def test_returns_list_of_dicts(self, mock_walk, usm):
        mock_walk.return_value = iter(
            [
                (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.1.0", "Linux")[0][3]),
                (None, None, None, _mock_cmd_result("1.3.6.1.2.1.1.2.0", "sysObjectID")[0][3]),
            ]
        )
        results = walk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.walkCmd")
    def test_empty_walk_returns_empty_list(self, mock_walk, usm):
        mock_walk.return_value = iter([])
        results = walk("192.168.1.1", "1.3.6.1.2.1.99", usm)
        assert results == []


class TestBulk:
    @patch("snmpv3_utils.core.query.bulkCmd")
    def test_returns_list_of_dicts(self, mock_bulk, usm):
        mock_bulk.return_value = iter(
            [
                (None, None, None, _mock_cmd_result()[0][3]),
            ]
        )
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert isinstance(results, list)
        assert all(set(r.keys()) == {"oid", "value"} for r in results)

    @patch("snmpv3_utils.core.query.bulkCmd")
    def test_returns_error_on_failure(self, mock_bulk, usm):
        mock_bulk.return_value = iter([("Timeout", None, None, [])])
        results = bulk("192.168.1.1", "1.3.6.1.2.1.1", usm)
        assert len(results) == 1
        assert "error" in results[0]
        assert set(results[0].keys()) == {"error", "host", "oid"}


class TestSet:
    @patch("snmpv3_utils.core.query.setCmd")
    def test_returns_success_dict(self, mock_set, usm):
        mock_set.return_value = iter([(None, None, None, [])])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "myrouter", "str", usm)
        assert result.get("status") == "ok"
        assert set(result.keys()) == {"status", "host", "oid", "value"}

    @patch("snmpv3_utils.core.query.setCmd")
    def test_returns_error_on_failure(self, mock_set, usm):
        mock_set.return_value = iter([("noSuchObject", None, None, [])])
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.5.0", "x", "str", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}

    def test_set_returns_error_with_host_on_invalid_type(self, usm):
        result = set_oid("192.168.1.1", "1.3.6.1.2.1.1.1.0", "val", "bogus", usm)
        assert "error" in result
        assert set(result.keys()) == {"error", "host", "oid"}
