"""
Documentation-CLI alignment tests.

These tests verify that the documentation accurately reflects the actual CLI behavior.
If these tests fail, either the docs or the CLI need to be updated to match.
"""

import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from sfdump.cli_simple import cli as sf_cli

DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "user-guide"


@pytest.fixture
def runner():
    return CliRunner()


class TestDocumentedCommandsExist:
    """Verify all commands mentioned in docs actually exist."""

    def test_getting_started_commands(self, runner):
        """Commands in getting-started.md should all work."""
        getting_started = DOCS_DIR / "getting-started.md"
        assert getting_started.exists(), "getting-started.md not found"

        content = getting_started.read_text()

        # Extract commands from code blocks (lines starting with "sf ")
        commands = re.findall(r"^sf (\w+)", content, re.MULTILINE)
        unique_commands = set(commands)

        for cmd in unique_commands:
            result = runner.invoke(sf_cli, [cmd, "--help"])
            assert result.exit_code == 0, f"Command 'sf {cmd}' failed: {result.output}"

    def test_quickstart_commands(self, runner):
        """Commands in quickstart.md should all work."""
        quickstart = DOCS_DIR / "quickstart.md"
        assert quickstart.exists(), "quickstart.md not found"

        content = quickstart.read_text()

        # Extract commands from code blocks
        commands = re.findall(r"^sf (\w+)", content, re.MULTILINE)
        unique_commands = set(commands)

        for cmd in unique_commands:
            result = runner.invoke(sf_cli, [cmd, "--help"])
            assert result.exit_code == 0, f"Command 'sf {cmd}' failed: {result.output}"


class TestQuickstartCommandTable:
    """Verify the command summary table in quickstart.md matches reality."""

    def test_command_table_accurate(self, runner):
        """The command table should list all sf commands accurately."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        # Extract command table entries: | `sf cmd` | description |
        table_commands = re.findall(r"\| `sf (\w+)` \|", content)

        # Get actual commands from CLI
        result = runner.invoke(sf_cli, ["--help"])
        assert result.exit_code == 0

        # Extract actual command names from help output
        actual_commands = re.findall(r"^\s+(\w+)\s+\w", result.output, re.MULTILINE)

        # Every documented command should exist
        for cmd in table_commands:
            assert cmd in actual_commands, (
                f"Command 'sf {cmd}' is documented but not in CLI. "
                f"Actual commands: {actual_commands}"
            )


class TestDocumentedOptionsExist:
    """Verify documented CLI options actually exist."""

    def test_dump_export_dir_option(self, runner):
        """The --export-dir option mentioned in FAQ should exist."""
        result = runner.invoke(sf_cli, ["dump", "--help"])
        assert result.exit_code == 0
        assert "--export-dir" in result.output, "FAQ references --export-dir but it doesn't exist"
        assert "-d" in result.output, "Short form -d should exist"

    def test_dump_retry_option(self, runner):
        """The --retry option mentioned in docs should exist."""
        result = runner.invoke(sf_cli, ["dump", "--help"])
        assert result.exit_code == 0
        assert "--retry" in result.output

    def test_dump_verbose_option(self, runner):
        """The -v/--verbose option mentioned in docs should exist."""
        result = runner.invoke(sf_cli, ["dump", "--help"])
        assert result.exit_code == 0
        assert "--verbose" in result.output
        assert "-v" in result.output


class TestGettingStartedAccuracy:
    """Verify getting-started.md content matches CLI behavior."""

    def test_documented_commands_match_help(self, runner):
        """Command descriptions in docs should roughly match --help."""
        getting_started = DOCS_DIR / "getting-started.md"
        content = getting_started.read_text()

        # Extract command reference table
        # Format: | `sf cmd` | description |
        table_entries = re.findall(r"\| `sf (\w+)` \| ([^|]+) \|", content)

        for cmd, doc_desc in table_entries:
            result = runner.invoke(sf_cli, [cmd, "--help"])
            assert result.exit_code == 0

            # Check that the help text contains key words from doc description
            # (loose matching - just verify they're about the same thing)
            doc_words = set(doc_desc.lower().split())
            key_words = doc_words - {"the", "a", "an", "to", "and", "or", "your", "from"}

            # At least one key word should appear in help
            help_lower = result.output.lower()
            matches = [w for w in key_words if w in help_lower]
            assert matches, (
                f"Command 'sf {cmd}' help doesn't match docs.\n"
                f"Doc says: {doc_desc.strip()}\n"
                f"Help says: {result.output[:200]}"
            )


class TestOutputExamplesPlausible:
    """Verify documented output examples are plausible."""

    def test_export_summary_format_documented(self):
        """The export summary format in quickstart.md should match code."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        # Check that key summary elements are documented
        assert "Export Summary" in content or "Location:" in content, (
            "Export summary format should be documented"
        )
        assert "Downloaded:" in content, "Downloaded count should be in example"
        assert "Missing:" in content, "Missing count should be in example"

    def test_sf_test_success_message_documented(self, runner):
        """The success message format from sf test should be documented."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        # The docs should mention what success looks like
        assert "Connection successful" in content, (
            "quickstart.md should show 'Connection successful' message"
        )


class TestTroubleshootingCoversCommonErrors:
    """Verify troubleshooting section covers likely errors."""

    def test_sf_client_id_error_documented(self):
        """Missing SF_CLIENT_ID error should be in troubleshooting."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        assert "SF_CLIENT_ID" in content, "Troubleshooting should mention SF_CLIENT_ID error"

    def test_connection_failed_documented(self):
        """Connection failure should be in troubleshooting."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        assert "Connection failed" in content or "connection failed" in content, (
            "Troubleshooting should mention connection failures"
        )

    def test_security_token_mentioned(self):
        """Security token requirement should be documented."""
        quickstart = DOCS_DIR / "quickstart.md"
        content = quickstart.read_text()

        assert "security token" in content.lower(), "Security token requirement should be mentioned"
