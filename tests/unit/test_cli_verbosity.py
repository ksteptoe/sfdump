from click.testing import CliRunner

from sfdump.cli import cli


def test_cli_verbose_flags_help():
    r1 = CliRunner().invoke(cli, ["-v"])
    r2 = CliRunner().invoke(cli, ["-vv"])
    assert r1.exit_code == 0 and r2.exit_code == 0
    assert "Usage:" in r1.output and "Usage:" in r2.output
