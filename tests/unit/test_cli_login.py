from click.testing import CliRunner

from sfdump.cli import cli


def test_login_success(monkeypatch, tmp_path):
    """
    login should:
      - call get_salesforce_token()
      - print success message
      - show the cache file path
      - show the shortened token preview
    """

    # Force Path.home() to a deterministic temporary directory
    monkeypatch.setattr("sfdump.cli.Path.home", lambda: tmp_path)

    # Fake token returned by sf_auth.get_salesforce_token
    def fake_get_salesforce_token():
        # 18 chars: preview uses first 10 and last 6
        return "0123456789ABCDEFGH"

    monkeypatch.setattr("sfdump.cli.get_salesforce_token", fake_get_salesforce_token)

    runner = CliRunner()
    result = runner.invoke(cli, ["login"])

    assert result.exit_code == 0
    out = result.output

    assert "Salesforce token refreshed and cached successfully" in out

    # Check that the reported cache file path is based on our tmp_path
    expected_cache = tmp_path / ".sfdump_token.json"
    assert str(expected_cache) in out

    # Preview logic: token[:10] + "..." + token[-6:]
    assert "Token preview:" in out
    assert "0123456789...CDEFGH" in out


def test_login_failure(monkeypatch):
    """
    If get_salesforce_token() raises, login should:
      - print an error message
      - exit with a non-zero code
    """

    def fake_get_salesforce_token():
        raise RuntimeError("boom")

    monkeypatch.setattr("sfdump.cli.get_salesforce_token", fake_get_salesforce_token)

    runner = CliRunner()
    result = runner.invoke(cli, ["login"])

    assert result.exit_code != 0
    assert "Login failed: boom" in result.output
