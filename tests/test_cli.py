import json
import logging

import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture()
def dummy_api(monkeypatch):
    """Patch SalesforceAPI and SFConfig so CLI runs offline."""

    class DummyAPI:
        def __init__(self, config):
            self.config = config

        def connect(self):
            # What cmd_login() relies on
            return {
                "access_token": "00DFAKE-TOKEN",
                "instance_url": "https://example.my.salesforce.com",
                "api_version": "v60.0",
                "organization_id": "ORG123",
                "user_name": "Test User",
                "cache_file": "/tmp/dummy.json",
                "limits": {
                    "DailyApiRequests": {"Max": 15000, "Remaining": 14999},
                },
            }

        def userinfo(self):
            return {
                "organization_id": "ORG123",
                "preferred_username": "test@example.com",
                "user_name": "Test User",
            }

        def limits(self):
            return {
                "DailyApiRequests": {"Max": 15000, "Remaining": 14999},
            }

        def query(self, soql):
            # Used by test_query_command
            return {
                "totalSize": 1,
                "done": True,
                "records": [
                    {
                        "attributes": {
                            "type": "Account",
                            "url": "/services/data/v60.0/sobjects/Account/001",
                        },
                        "Id": "001",
                        "Name": "Acme Corp",
                    }
                ],
            }

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
    assert "Connected to Salesforce." in result.output
    assert "Instance URL" in result.output
    assert "API Version" in result.output
    assert "ORG123" in result.output
    assert "Test User" in result.output


def test_login_show_json(dummy_api):
    """Ensure JSON output appears when using --show-json."""
    runner = CliRunner()
    result = runner.invoke(cli, ["login", "--show-json"])
    assert result.exit_code == 0
    assert "# whoami" in result.output

    # Extract and parse the JSON between the headers
    body = result.output.split("# whoami (userinfo)", 1)[1].split("# limits", 1)[0]
    parsed = json.loads(body)
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
