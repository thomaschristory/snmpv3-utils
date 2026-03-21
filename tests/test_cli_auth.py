# tests/test_cli_auth.py
from unittest.mock import patch

from typer.testing import CliRunner

from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestAuthCheck:
    @patch("snmpv3_utils.cli.auth.core_check_creds")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_check_success(self, mock_usm, mock_creds, mock_check):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_check.return_value = {"status": "ok", "host": "192.168.1.1", "username": "admin"}
        result = runner.invoke(app, ["auth", "check", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.auth.core_check_creds")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_check_failure_exits_nonzero(self, mock_usm, mock_creds, mock_check):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_check.return_value = {  # noqa: E501
            "status": "failed",
            "host": "192.168.1.1",
            "error": "wrongDigest",
        }
        result = runner.invoke(app, ["auth", "check", "192.168.1.1", "--format", "json"])
        assert result.exit_code != 0


class TestAuthBulk:
    def test_bulk_file_not_found(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist.csv"
        result = runner.invoke(app, ["auth", "bulk", "192.168.1.1", "--file", str(nonexistent)])
        assert result.exit_code != 0
        assert "File not found" in result.output

    @patch("snmpv3_utils.cli.auth.core_bulk_check")
    def test_bulk_success(self, mock_bulk, tmp_path):
        csv_file = tmp_path / "creds.csv"
        csv_file.write_text(
            "username,auth_protocol,auth_key,priv_protocol,priv_key,security_level\n"
        )
        mock_bulk.return_value = [{"status": "ok", "host": "192.168.1.1", "username": "admin"}]
        result = runner.invoke(
            app,
            ["auth", "bulk", "192.168.1.1", "--file", str(csv_file), "--format", "json"],
        )
        assert result.exit_code == 0
