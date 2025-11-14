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
