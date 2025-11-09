import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture
def runner():
    """Fixture that provides a Click test runner."""
    return CliRunner()


def test_cli_shows_help(runner):
    """Verify that running without arguments shows help."""
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "login" in result.output or "query" in result.output


def test_cli_login_missing_env(runner, monkeypatch):
    """Ensure login fails when environment variables are missing."""
    for var in ["SF_USERNAME", "SF_PASSWORD", "SF_TOKEN"]:
        monkeypatch.delenv(var, raising=False)

    result = runner.invoke(cli, ["login"])
    assert result.exit_code != 0
    assert "Missing" in result.output or "Error" in result.output
