import json
import logging

import pytest
from click.testing import CliRunner

from sfdump.cli import cli


def test_cli_version_option():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "sfdump" in result.output.lower()


@pytest.mark.parametrize("verbosity", [[], ["-v"], ["-vv"]])
def test_login_command(verbosity):
    """Run `sfdump login` with different verbosity levels."""
    runner = CliRunner()
    args = verbosity + ["login"]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0
    assert "Connected to Salesforce." in result.output
    assert "Instance URL" in result.output
    assert "API Version" in result.output
    assert "ORG123" in result.output
    assert "Test User" in result.output


def test_login_show_json():
    """Ensure JSON output appears when using --show-json."""
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--show-json"])
    assert result.exit_code == 0
    assert "# whoami" in result.output

    # Valid JSON section should parse correctly
    body = result.output.split("# whoami (userinfo)", 1)[1].split("# limits", 1)[0]
    parsed = json.loads(body)
    assert parsed["organization_id"] == "ORG123"


def test_query_command():
    """Run a simple SOQL query and confirm printed JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT Id FROM Account LIMIT 1"])
    assert result.exit_code == 0
    assert "Acme" in result.output


def test_logging_levels(caplog):
    """Verify that -v/-vv adjust log level."""
    runner = CliRunner()
    with caplog.at_level(logging.DEBUG):
        result = runner.invoke(cli, ["-vv", "login"])
    assert result.exit_code == 0
    assert "Connected" in caplog.text or "Instance" in result.output
