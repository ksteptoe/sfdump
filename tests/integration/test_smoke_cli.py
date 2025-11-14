from click.testing import CliRunner

from sfdump.cli import cli


def test_integration_cli_help_runs():
    """
    Very small integration smoke test.

    Runs the real CLI entry point with --help to ensure:
      - sfdump.cli imports correctly
      - click wiring is intact
      - help text can be generated without error
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Just a light sanity check on the output
    assert "SF Dump CLI" in result.output or "Use subcommands" in result.output
