# tests/test_auth.py
import asyncio
import csv
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from snmpv3_utils.core.auth import _parse_row_to_usm, bulk_check, check_creds


@pytest.fixture
def usm(usm_no_auth):
    return usm_no_auth


class TestCheckCreds:
    @patch("snmpv3_utils.core.auth.get")
    def test_success_when_get_returns_value(self, mock_get, usm):
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        result = check_creds("192.168.1.1", usm)
        assert result["status"] == "ok"
        assert result["host"] == "192.168.1.1"
        assert set(result.keys()) == {"status", "host", "username", "sysdescr"}
        assert isinstance(result["sysdescr"], str)

    @patch("snmpv3_utils.core.auth.get")
    def test_failure_when_get_returns_error(self, mock_get, usm):
        mock_get.return_value = {"error": "wrongDigest"}
        result = check_creds("192.168.1.1", usm)
        assert result["status"] == "failed"
        assert "error" in result
        assert set(result.keys()) == {"status", "host", "username", "error"}


class TestBulkCheck:
    def _make_csv(self, rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "username",
                "auth_protocol",
                "auth_key",
                "priv_protocol",
                "priv_key",
                "security_level",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_bulk_returns_result_per_row(self, mock_get, mock_transport, tmp_path):
        mock_transport.return_value = MagicMock()
        mock_get.side_effect = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
            {"error": "wrongDigest", "host": "192.168.1.1", "oid": "1.3.6.1.2.1.1.1.0"},
        ]
        csv_content = self._make_csv(
            [
                {
                    "username": "admin",
                    "auth_protocol": "SHA256",
                    "auth_key": "pass",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
                {
                    "username": "wrong",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "failed"
        assert all(
            set(r.keys())
            in ({"status", "host", "username", "sysdescr"}, {"status", "host", "username", "error"})
            for r in results
        )

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    def test_bulk_returns_failed_on_invalid_credentials(self, mock_transport, tmp_path):
        """Rows with invalid credential combinations return status=failed without raising."""
        mock_transport.return_value = MagicMock()
        csv_content = self._make_csv(
            [
                {
                    "username": "bad",
                    "auth_protocol": "SHA256",
                    "auth_key": "",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "error" in results[0]

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    def test_bulk_handles_invalid_enum_in_csv(self, mock_transport, tmp_path):
        """Unrecognised enum values in CSV are returned as per-row failures."""
        mock_transport.return_value = MagicMock()
        csv_content = self._make_csv(
            [
                {
                    "username": "bad",
                    "auth_protocol": "SHA384",
                    "auth_key": "key",
                    "priv_protocol": "AES128",
                    "priv_key": "priv",
                    "security_level": "authPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "error" in results[0]


class TestBulkCheckConcurrency:
    """Tests for the async gather path in bulk_check."""

    def _make_csv(self, rows: list[dict]) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf,
            fieldnames=[
                "username",
                "auth_protocol",
                "auth_key",
                "priv_protocol",
                "priv_key",
                "security_level",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue()

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_results_preserve_csv_row_order(self, mock_get, mock_transport, tmp_path):
        """Results come back in CSV row order regardless of completion order."""
        mock_transport.return_value = MagicMock()
        mock_get.side_effect = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-A"},
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-B"},
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Device-C"},
        ]
        csv_content = self._make_csv(
            [
                {
                    "username": "a",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
                {
                    "username": "b",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
                {
                    "username": "c",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 3
        assert results[0]["username"] == "a"
        assert results[1]["username"] == "b"
        assert results[2]["username"] == "c"

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_invalid_rows_inline_with_valid(self, mock_get, mock_transport, tmp_path):
        """Invalid CSV rows produce error results at their original index."""
        mock_transport.return_value = MagicMock()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        csv_content = self._make_csv(
            [
                {
                    "username": "good",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
                {
                    "username": "bad",
                    "auth_protocol": "SHA384",
                    "auth_key": "k",
                    "priv_protocol": "AES128",
                    "priv_key": "p",
                    "security_level": "authPriv",
                },
                {
                    "username": "good2",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                },
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path)
        assert len(results) == 3
        assert results[0]["status"] == "ok"
        assert results[0]["username"] == "good"
        assert results[1]["status"] == "failed"
        assert results[1]["username"] == "bad"
        assert "error" in results[1]
        assert results[2]["status"] == "ok"
        assert results[2]["username"] == "good2"

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_max_concurrent_none_runs_all(self, mock_get, mock_transport, tmp_path):
        """max_concurrent=None fires all checks without a semaphore."""
        mock_transport.return_value = MagicMock()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
        csv_content = self._make_csv(
            [
                {
                    "username": f"user{i}",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                }
                for i in range(5)
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path, max_concurrent=None)
        assert len(results) == 5
        assert all(r["status"] == "ok" for r in results)

    @patch("snmpv3_utils.core.auth.UdpTransportTarget.create", new_callable=AsyncMock)
    @patch("snmpv3_utils.core.auth._get", new_callable=AsyncMock)
    def test_max_concurrent_limits_parallelism(self, mock_get, mock_transport, tmp_path):
        """max_concurrent=2 limits how many checks run at once."""
        mock_transport.return_value = MagicMock()
        peak = 0
        current = 0

        async def _tracking_get(*args, **kwargs):
            nonlocal peak, current
            current += 1
            peak = max(peak, current)
            await asyncio.sleep(0)  # yield to event loop
            result = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}
            current -= 1
            return result

        mock_get.side_effect = _tracking_get
        csv_content = self._make_csv(
            [
                {
                    "username": f"user{i}",
                    "auth_protocol": "",
                    "auth_key": "",
                    "priv_protocol": "",
                    "priv_key": "",
                    "security_level": "noAuthNoPriv",
                }
                for i in range(5)
            ]
        )
        csv_path = tmp_path / "creds.csv"
        csv_path.write_text(csv_content)

        results = bulk_check("192.168.1.1", csv_path, max_concurrent=2)
        assert len(results) == 5
        assert all(r["status"] == "ok" for r in results)
        assert peak <= 2


class TestParseRowToUsm:
    def test_valid_authpriv_row(self):
        row = {
            "username": "admin",
            "auth_protocol": "SHA256",
            "auth_key": "authpass",
            "priv_protocol": "AES128",
            "priv_key": "privpass",
            "security_level": "authPriv",
        }
        usm = _parse_row_to_usm(row)
        assert usm.userName == "admin"

    def test_valid_noauthnopriv_row(self):
        row = {
            "username": "public",
            "auth_protocol": "",
            "auth_key": "",
            "priv_protocol": "",
            "priv_key": "",
            "security_level": "noAuthNoPriv",
        }
        usm = _parse_row_to_usm(row)
        assert usm.userName == "public"

    def test_invalid_auth_protocol_raises(self):
        row = {
            "username": "bad",
            "auth_protocol": "SHA384",
            "auth_key": "key",
            "priv_protocol": "AES128",
            "priv_key": "priv",
            "security_level": "authPriv",
        }
        with pytest.raises(ValueError):
            _parse_row_to_usm(row)

    def test_missing_auth_key_raises(self):
        row = {
            "username": "bad",
            "auth_protocol": "SHA256",
            "auth_key": "",
            "priv_protocol": "AES128",
            "priv_key": "priv",
            "security_level": "authPriv",
        }
        with pytest.raises(ValueError):
            _parse_row_to_usm(row)
