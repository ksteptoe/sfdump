import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_salesforce_api(monkeypatch):
    """Mock SalesforceAPI and SFConfig so no real network calls occur."""

    class DummyAPI:
        def __init__(self, config):
            self.instance_url = "https://example.my.salesforce.com"
            self.api_version = "v59.0"

        def connect(self):
            return True

        def whoami(self):
            return {
                "organization_id": "ORG123",
                "user_id": "USER123",
                "preferred_username": "test@example.com",
                "name": "Test User",
            }

        def limits(self):
            return {"DailyApiRequests": {"Max": 15000, "Remaining": 14999}}

    class DummyConfig:
        @classmethod
        def from_env(cls):
            return cls()

    # Patch the symbols used inside CLI
    monkeypatch.setattr("sfdump.cli.SalesforceAPI", DummyAPI)
    monkeypatch.setattr("sfdump.cli.SFConfig", DummyConfig)
    return DummyAPI


def test_login_success(runner, monkeypatch):
    """Simulate successful login flow."""
    # Set minimal environment variables
    monkeypatch.setenv("SF_USERNAME", "test@example.com")
    monkeypatch.setenv("SF_PASSWORD", "pw")
    monkeypatch.setenv("SF_TOKEN", "token")

    result = runner.invoke(cli, ["login"])
    assert result.exit_code == 0
    assert "Instance URL" in result.output
    assert "API Version" in result.output
    assert "Test User" in result.output
