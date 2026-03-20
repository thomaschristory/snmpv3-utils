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
