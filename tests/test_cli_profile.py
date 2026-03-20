# tests/test_cli_profile.py
from unittest.mock import patch
from typer.testing import CliRunner
from snmpv3_utils.cli.main import app

runner = CliRunner()


def test_profile_add_and_list(tmp_path):
    with patch("snmpv3_utils.config.get_profiles_path", return_value=tmp_path / "profiles.toml"):
        result = runner.invoke(app, [
            "profile", "add", "testprofile",
            "--username", "admin",
            "--security-level", "noAuthNoPriv",
        ])
        assert result.exit_code == 0
        assert "saved" in result.output

        result = runner.invoke(app, ["profile", "list"])
        assert result.exit_code == 0
        assert "testprofile" in result.output


def test_profile_delete(tmp_path):
    with patch("snmpv3_utils.config.get_profiles_path", return_value=tmp_path / "profiles.toml"):
        runner.invoke(app, ["profile", "add", "todelete", "--username", "x"])
        result = runner.invoke(app, ["profile", "delete", "todelete"])
        assert result.exit_code == 0
        assert "deleted" in result.output
