# tests/test_cli_query.py
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


class TestQueryGet:
    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_get_outputs_json(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"}

        result = runner.invoke(app, [
            "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"
        ])
        assert result.exit_code == 0
        assert "Linux" in result.output

    @patch("snmpv3_utils.cli.query.core_get")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_get_exits_nonzero_on_error(self, mock_usm, mock_creds, mock_get):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_get.return_value = {"error": "Timeout"}

        result = runner.invoke(app, [
            "query", "get", "192.168.1.1", "1.3.6.1.2.1.1.1.0", "--format", "json"
        ])
        assert result.exit_code != 0


class TestQueryWalk:
    @patch("snmpv3_utils.cli.query.core_walk")
    @patch("snmpv3_utils.cli.query.resolve_credentials")
    @patch("snmpv3_utils.cli.query.build_usm_user")
    def test_walk_outputs_json_array(self, mock_usm, mock_creds, mock_walk):
        from snmpv3_utils.security import Credentials
        mock_creds.return_value = Credentials()
        mock_usm.return_value = object()
        mock_walk.return_value = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "Linux"},
        ]
        result = runner.invoke(app, [
            "query", "walk", "192.168.1.1", "1.3.6.1.2.1.1", "--format", "json"
        ])
        assert result.exit_code == 0
        assert "1.3.6.1.2.1.1.1.0" in result.output
