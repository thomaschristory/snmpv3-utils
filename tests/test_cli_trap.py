# tests/test_cli_trap.py
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
        result = runner.invoke(app, ["trap", "listen", "--port", "16200"])
        assert result.exit_code != 0
        assert "not implemented" in result.output.lower()
