import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def mock_api(monkeypatch):
    class DummyAPI:
        def __init__(self, cfg):
            self.instance_url = "https://example"
            self.api_version = "v59.0"

        def connect(self):  # no-op
            return True

        def query(self, soql):
            assert "SELECT" in soql
            return {"totalSize": 1, "records": [{"Id": "001XXXX"}]}

    class DummyCfg:
        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr("sfdump.cli.SalesforceAPI", DummyAPI)
    monkeypatch.setattr("sfdump.cli.SFConfig", DummyCfg)


def test_query_pretty_json(runner):
    res = runner.invoke(cli, ["query", "SELECT Id FROM Account", "--pretty"])
    assert res.exit_code == 0
    assert '"records":' in res.output
    assert '"Id": "001' in res.output
