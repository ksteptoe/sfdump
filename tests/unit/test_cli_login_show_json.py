import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_salesforce_api(monkeypatch):
    """Mock the API to hit all branches in login, including show-json output."""

    class DummyAPI:
        def __init__(self, config):
            self.instance_url = "https://example.my.salesforce.com"
            self.api_version = "v59.0"

        def connect(self):
            return True

        def whoami(self):
            return {
                "organization_id": "ORGID",
                "user_id": "USERID",
                "preferred_username": "demo@example.com",
                "name": "Demo User",
                "email": "demo@example.com",
            }

        def limits(self):
            return {"DailyApiRequests": {"Max": 15000, "Remaining": 14998}}

    class DummyConfig:
        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr("sfdump.cli.SalesforceAPI", DummyAPI)
    monkeypatch.setattr("sfdump.cli.SFConfig", DummyConfig)


def test_login_with_show_json(runner, monkeypatch):
    """Covers the JSON-printing branch in cmd_login."""
    monkeypatch.setenv("SF_USERNAME", "demo@example.com")
    monkeypatch.setenv("SF_PASSWORD", "pw")
    monkeypatch.setenv("SF_TOKEN", "tok")

    result = runner.invoke(cli, ["login", "--show-json"])
    assert result.exit_code == 0
    assert "Instance URL" in result.output
    assert "# whoami" in result.output
    assert '"organization_id": "ORGID"' in result.output
    assert '"DailyApiRequests"' in result.output
