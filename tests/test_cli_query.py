# tests/test_cli_query.py
from unittest.mock import patch

from typer.testing import CliRunner

from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestQueryGet:
    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_get_outputs_json(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code == 0
        assert "Linux" in result.output

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_get_exits_nonzero_on_error(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"error": "Timeout"}

        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code != 0


class TestQueryWalk:
    @patch("snmpv3_utils.cli.query.core_walk")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_walk_outputs_json_array(self, mock_usm, mock_creds, mock_walk):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_walk.return_value = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
        ]
        result = runner.invoke(
            app, ["query", "walk", "192.168.1.1", "1.3.6.1.2.1.1", "--format", "json"]
        )
        assert result.exit_code == 0
        assert "1.3.6.1.2.1.1.1.0" in result.output

    @patch("snmpv3_utils.cli.query.core_walk")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_walk_exits_nonzero_on_error(self, mock_usm, mock_creds, mock_walk):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_walk.return_value = [{"error": "Timeout", "host": "192.168.1.1", "oid": "1.3.6.1"}]
        result = runner.invoke(
            app, ["query", "walk", "192.168.1.1", "1.3.6.1.2.1.1", "--format", "json"]
        )
        assert result.exit_code != 0


class TestQueryGetnext:
    @patch("snmpv3_utils.cli.query.core_getnext")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_getnext_outputs_json(self, mock_usm, mock_creds, mock_getnext):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_getnext.return_value = {"oid": "1.3.6.1.2.1.1.2.0", "value": "sysObjectID"}
        result = runner.invoke(
            app, ["query", "getnext", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"]
        )
        assert result.exit_code == 0
        assert "sysObjectID" in result.output


class TestCredentialErrors:
    """Errors from resolve_credentials must produce clean CLI output, not raw tracebacks."""

    def test_nonexistent_profile_shows_clean_error(self):
        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--profile", "nonexistent"]
        )
        assert result.exit_code != 0
        assert "Error:" in result.output
        assert "Traceback" not in result.output

    @patch("snmpv3_utils.cli._options.resolve_credentials")
    def test_resolve_credentials_keyerror_shows_clean_error(self, mock_resolve):
        mock_resolve.side_effect = KeyError("badprofile")
        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "-u", "test"]
        )
        assert result.exit_code != 0
        assert "Error:" in result.output
        assert "Traceback" not in result.output

    @patch("snmpv3_utils.cli._options.resolve_credentials")
    def test_resolve_credentials_valueerror_shows_clean_error(self, mock_resolve):
        mock_resolve.side_effect = ValueError("invalid auth protocol")
        result = runner.invoke(
            app, ["query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "-u", "test"]
        )
        assert result.exit_code != 0
        assert "Error:" in result.output
        assert "Traceback" not in result.output


class TestQuerySet:
    @patch("snmpv3_utils.cli.query.core_set")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_set_outputs_json_on_success(self, mock_usm, mock_creds, mock_set):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_set.return_value = {  # noqa: E501
            "status": "ok",
            "host": "192.168.1.1",
            "oid": "1.3.6.1.2.1.1.5.0",
            "value": "myrouter",
        }
        result = runner.invoke(
            app,
            ["query", "set", "192.168.1.1", "1.3.6.1.2.1.1.5.0", "myrouter", "--format", "json"],
        )
        assert result.exit_code == 0
        assert "ok" in result.output

    @patch("snmpv3_utils.cli.query.core_set")
    @patch("snmpv3_utils.cli._options.resolve_credentials")
    @patch("snmpv3_utils.cli._options.build_usm_user")
    def test_set_exits_nonzero_on_error(self, mock_usm, mock_creds, mock_set):
        from snmpv3_utils.security import Credentials

        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_set.return_value = {"error": "noSuchObject"}
        result = runner.invoke(
            app, ["query", "set", "192.168.1.1", "1.3.6.1.2.1.1.5.0", "x", "--format", "json"]
        )
        assert result.exit_code != 0
