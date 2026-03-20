# tests/test_auth.py
import csv
import io
from unittest.mock import patch

import pytest

from snmpv3_utils.core.auth import bulk_check, check_creds


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

    @patch("snmpv3_utils.core.auth.get")
    def test_failure_when_get_returns_error(self, mock_get, usm):
        mock_get.return_value = {"error": "wrongDigest"}
        result = check_creds("192.168.1.1", usm)
        assert result["status"] == "failed"
        assert "error" in result


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

    @patch("snmpv3_utils.core.auth.check_creds")
    def test_bulk_returns_result_per_row(self, mock_check, tmp_path):
        mock_check.side_effect = [
            {"status": "ok", "host": "192.168.1.1", "username": "admin"},
            {"status": "failed", "host": "192.168.1.1", "username": "wrong"},
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

    def test_bulk_returns_failed_on_invalid_credentials(self, tmp_path):
        """Rows with invalid credential combinations return status=failed without raising."""
        csv_content = self._make_csv(
            [
                # authPriv with no auth_key triggers ValueError in build_usm_user
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

    def test_bulk_handles_invalid_enum_in_csv(self, tmp_path):
        """Unrecognised enum values in CSV are returned as per-row failures."""
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
