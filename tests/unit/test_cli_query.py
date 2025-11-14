import json

from click.testing import CliRunner

from sfdump.cli import cli


def test_query_success(monkeypatch):
    """
    query should call run_salesforce_query() and print JSON.
    """

    def fake_run_salesforce_query(soql: str):
        assert soql == "SELECT Id FROM Account LIMIT 1"
        return {
            "totalSize": 1,
            "done": True,
            "records": [
                {"Id": "001", "Name": "Acme Corp"},
            ],
        }

    monkeypatch.setattr("sfdump.cli.run_salesforce_query", fake_run_salesforce_query)

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT Id FROM Account LIMIT 1"])

    assert result.exit_code == 0
    out = result.output.strip()

    data = json.loads(out)
    assert data["totalSize"] == 1
    assert data["records"][0]["Name"] == "Acme Corp"


def test_query_pretty_print(monkeypatch):
    """
    --pretty should cause indent=2 JSON output.
    """

    def fake_run_salesforce_query(soql: str):
        return {"foo": "bar"}

    monkeypatch.setattr("sfdump.cli.run_salesforce_query", fake_run_salesforce_query)

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "--pretty", "SELECT 1 FROM Foo"])

    assert result.exit_code == 0
    # Very crude check that it's multi-line / indented JSON
    assert "{\n  " in result.output


def test_query_error(monkeypatch):
    """
    If run_salesforce_query() raises, query should print an error line
    but *not* abort the whole CLI.
    """

    def fake_run_salesforce_query(soql: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("sfdump.cli.run_salesforce_query", fake_run_salesforce_query)

    runner = CliRunner()
    result = runner.invoke(cli, ["query", "SELECT Id FROM Bad"])

    # We don't call click.Abort() here, so exit code remains 0
    assert result.exit_code == 0
    assert "Error: boom" in result.output
