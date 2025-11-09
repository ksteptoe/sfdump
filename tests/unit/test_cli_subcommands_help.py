import pytest
from click.testing import CliRunner

from sfdump.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize("sub", ["login", "query", "objects", "files", "csv", "manifest"])
def test_subcommand_help(runner, sub):
    res = runner.invoke(cli, [sub, "--help"])
    assert res.exit_code == 0
    assert "Usage:" in res.output
