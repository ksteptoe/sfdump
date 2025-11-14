from click.testing import CliRunner

from sfdump.cli import cli


def test_cli_help_shows_usage():
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    # From cli() docstring and subcommands
    assert "SF Dump CLI" in result.output
    assert "login" in result.output
    assert "query" in result.output


def test_cli_version_option():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    # click.version_option prints something like "sfdump, version X.Y.Z"
    assert "sfdump" in result.output.lower()
