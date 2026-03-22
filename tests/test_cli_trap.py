# tests/test_cli_trap.py
import json
from unittest.mock import patch

from typer.testing import CliRunner

from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestTrapSend:
    @patch("snmpv3_utils.cli.trap.core_send_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_send_returns_ok(self, mock_usm, mock_creds, mock_trap):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_trap.return_value = {  # noqa: E501
            "status": "ok",
            "host": "192.168.1.1",
            "type": "trap",
            "inform": False,
        }

        result = runner.invoke(app, ["trap", "send", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 0
        assert "ok" in result.output

    @patch("snmpv3_utils.cli.trap.core_send_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_send_inform_flag(self, mock_usm, mock_creds, mock_trap):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_trap.return_value = {  # noqa: E501
            "status": "ok",
            "host": "192.168.1.1",
            "type": "inform",
            "inform": True,
        }

        result = runner.invoke(app, ["trap", "send", "192.168.1.1", "--inform", "--format", "json"])
        assert result.exit_code == 0
        _, kwargs = mock_trap.call_args
        assert kwargs.get("inform") is True or mock_trap.call_args[0][2] is True


class TestTrapListen:
    def test_listen_exits_nonzero_with_not_implemented_message(self):
        """The listen stub should exit 1 and print the NotImplementedError message."""
        result = runner.invoke(app, ["trap", "listen", "--port", "16200", "--username", "test"])
        assert result.exit_code != 0
        assert "not implemented" in result.output.lower()


class TestTrapSendValidation:
    def test_send_no_username_shows_error(self):
        """Missing username should show a clear error, not a pysnmp traceback."""
        result = runner.invoke(app, ["trap", "send", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 1
        assert "username is required" in result.output.lower()


class TestTrapStressValidation:
    def test_stress_no_username_shows_error(self):
        """Missing username should show a clear error, not a pysnmp traceback."""
        result = runner.invoke(app, ["trap", "stress", "192.168.1.1", "--format", "json"])
        assert result.exit_code == 1
        assert "username is required" in result.output.lower()

    def test_stress_short_auth_key_shows_error(self):
        """Short auth key should show a clean error, not a pysnmp WrongValueError."""
        result = runner.invoke(
            app,
            [
                "trap",
                "stress",
                "192.168.1.1",
                "-u",
                "admin",
                "--auth-protocol",
                "SHA256",
                "--auth-key",
                "short",
                "--priv-protocol",
                "AES256",
                "--priv-key",
                "short",
                "--security-level",
                "authPriv",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 1
        assert "at least 8 characters" in result.output.lower()
        assert "WrongValueError" not in result.output

    def test_stress_short_priv_key_shows_error(self):
        """Short priv key should show a clean error, not a pysnmp WrongValueError."""
        result = runner.invoke(
            app,
            [
                "trap",
                "stress",
                "192.168.1.1",
                "-u",
                "admin",
                "--auth-protocol",
                "SHA256",
                "--auth-key",
                "longenoughkey",
                "--priv-protocol",
                "AES256",
                "--priv-key",
                "short",
                "--security-level",
                "authPriv",
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 1
        assert "at least 8 characters" in result.output.lower()
        assert "WrongValueError" not in result.output


class TestTrapStress:
    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_json_output(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "192.168.1.1",
            "sent": 10,
            "errors": 1,
            "success_rate": "90.0%",
            "duration_s": 1.5,
            "rate_achieved": 6.7,
            "error_samples": ["timeout"],
        }

        result = runner.invoke(
            app, ["trap", "stress", "192.168.1.1", "--count", "10", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["sent"] == 10
        assert data["errors"] == 1
        assert "success_rate" in data

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_0_on_partial_success(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h",
            "sent": 10,
            "errors": 5,
            "success_rate": "50.0%",
            "duration_s": 1.0,
            "rate_achieved": 10.0,
            "error_samples": [],
        }

        result = runner.invoke(app, ["trap", "stress", "h", "--count", "10", "--format", "json"])
        assert result.exit_code == 0

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_1_on_all_errors(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h",
            "sent": 10,
            "errors": 10,
            "success_rate": "0.0%",
            "duration_s": 1.0,
            "rate_achieved": 10.0,
            "error_samples": ["err"],
        }

        result = runner.invoke(app, ["trap", "stress", "h", "--count", "10", "--format", "json"])
        assert result.exit_code == 1

    @patch("snmpv3_utils.cli.trap.core_stress_trap")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_stress_exit_code_1_on_zero_sent(self, mock_usm, mock_creds, mock_stress):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_stress.return_value = {
            "host": "h",
            "sent": 0,
            "errors": 0,
            "success_rate": "N/A",
            "duration_s": 0.0,
            "rate_achieved": 0.0,
            "error_samples": [],
        }

        result = runner.invoke(app, ["trap", "stress", "h", "--count", "0", "--format", "json"])
        assert result.exit_code == 1
