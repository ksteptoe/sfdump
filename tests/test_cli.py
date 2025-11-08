import json
import logging

import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture()
def dummy_api(monkeypatch):
    """Patch SalesforceAPI and SFConfig so CLI runs offline."""

    class DummyAPI:
        def __init__(self, cfg=None):
            self.instance_url = "https://example.my.salesforce.com"
            self.api_version = "v62.0"

        def connect(self):
            pass

        def whoami(self):
            return {
                "organization_id": "ORG123",
                "user_id": "USR456",
                "email": "user@example.com",
                "name": "Test User",
            }

        def limits(self):
            return {"DailyApiRequests": {"Max": 15000, "Remaining": 14999}}

        def query(self, soql):
            return {"records": [{"Id": "001", "Name": "Acme"}]}

    class DummyConfig:
        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr("sfdump.cli.SalesforceAPI", DummyAPI)
    monkeypatch.setattr("sfdump.cli.SFConfig", DummyConfig)
    return DummyAPI


def test_cli_version_option():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "sfdump" in result.output.lower()


@pytest.mark.parametrize("verbosity", [[], ["-v"], ["-vv"]])
def test_login_command(dummy_api, verbosity):
    """Run `sfdump login` with different verbosity levels."""
    runner = CliRunner()
    args = verbosity + ["login"]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0
    assert "Instance URL" in result.output
    assert "API Version" in result.output
    assert "ORG123" in result.output


def test_login_show_json(dummy_api):
    """Ensure JSON output appears when using --show-json."""
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--show-json"])
    assert result.exit_code == 0
    assert "# whoami" in result.output
    # Valid JSON section should parse correctly
    parsed = json.loads(result.output.split("# whoami (userinfo)")[1].split("# limits")[0])
    assert parsed["organization_id"] == "ORG123"


def test_query_command(dummy_api):
    """Run a simple SOQL query and confirm printed JSON."""
    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT Id FROM Account LIMIT 1"])
    assert result.exit_code == 0
    assert "Acme" in result.output


def test_logging_levels(monkeypatch, dummy_api, caplog):
    """Verify that -v/-vv adjust log level."""
    runner = CliRunner()

    with caplog.at_level(logging.DEBUG):
        result = runner.invoke(cli, ["-vv", "login"])
    assert result.exit_code == 0
    assert "Connected" in caplog.text or "Instance" in result.output
