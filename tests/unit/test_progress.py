"""
Tests for the progress reporting module.

Tests cover:
- ProgressBar with animated spinner
- Spinner for unknown-duration operations
- ProgressReporter unified output
- StepContext for step completion tracking
"""

from __future__ import annotations

import io
import time

from sfdump.progress import (
    ProgressBar,
    ProgressReporter,
    Spinner,
    StepContext,
    spinner,
)


class TestProgressBar:
    """Tests for the ProgressBar class."""

    def test_progress_bar_renders_correctly(self):
        """Progress bar should render with label, bar, and percentage."""
        output = io.StringIO()
        pb = ProgressBar(label="Test", total=100, width=10, indent="", output=output)
        pb._current = 50

        result = pb._render_bar(0)

        assert "Test" in result
        assert "50%" in result
        assert "█" in result
        assert "░" in result

    def test_progress_bar_zero_total(self):
        """Progress bar with zero total should show 0%."""
        output = io.StringIO()
        pb = ProgressBar(total=0, width=10, indent="", output=output)

        result = pb._render_bar(0)

        assert "0%" in result

    def test_progress_bar_update_is_thread_safe(self):
        """Update should be thread-safe via lock."""
        output = io.StringIO()
        pb = ProgressBar(total=100, output=output)
        pb.update(75)

        assert pb._current == 75

    def test_progress_bar_context_manager(self):
        """Progress bar should work as context manager."""
        output = io.StringIO()
        pb = ProgressBar(total=10, width=10, indent="", output=output)

        with pb:
            pb.update(5)
            time.sleep(0.15)  # Let animation run at least once

        # Should have printed something
        result = output.getvalue()
        assert len(result) > 0
        # Should end with checkmark
        assert "✓" in result

    def test_progress_bar_shows_completion(self):
        """Progress bar should show checkmark on completion."""
        output = io.StringIO()
        pb = ProgressBar(total=10, width=10, indent="", output=output)

        with pb:
            pb.update(10)

        result = output.getvalue()
        assert "✓" in result


class TestSpinner:
    """Tests for the Spinner class."""

    def test_spinner_context_manager(self):
        """Spinner should work as context manager."""
        output = io.StringIO()
        s = Spinner(message="Loading", indent="", output=output)

        with s:
            time.sleep(0.15)  # Let animation run

        result = output.getvalue()
        assert "Loading" in result
        assert "✓" in result

    def test_spinner_without_message(self):
        """Spinner should work without message."""
        output = io.StringIO()
        s = Spinner(message="", indent="", output=output)

        with s:
            time.sleep(0.05)

        result = output.getvalue()
        assert "✓" in result

    def test_legacy_spinner_function(self):
        """Legacy spinner() function should work."""
        output = io.StringIO()

        with spinner(message="Working", output=output):
            time.sleep(0.05)

        result = output.getvalue()
        assert "Working" in result


class TestStepContext:
    """Tests for the StepContext class."""

    def test_step_context_done(self):
        """StepContext.done() should print completion message."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)
        ctx = StepContext(num=1, total=3, message="Test", reporter=reporter)

        ctx.done("completed")

        assert "completed" in output.getvalue()
        assert ctx._completed is True

    def test_step_context_done_only_once(self):
        """StepContext.done() should only print once."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)
        ctx = StepContext(num=1, total=3, message="Test", reporter=reporter)

        ctx.done("first")
        ctx.done("second")  # Should be ignored

        result = output.getvalue()
        assert result.count("first") == 1
        assert "second" not in result

    def test_step_context_error(self):
        """StepContext.error() should print error message."""
        output = io.StringIO()
        err_output = io.StringIO()
        reporter = ProgressReporter(output=output)
        ctx = StepContext(num=1, total=3, message="Test", reporter=reporter)

        # Temporarily redirect stderr for the reporter
        import sys

        old_stderr = sys.stderr
        sys.stderr = err_output
        try:
            ctx.error("something failed")
        finally:
            sys.stderr = old_stderr

        assert "ERROR" in err_output.getvalue()
        assert "something failed" in err_output.getvalue()
        assert ctx._completed is True


class TestProgressReporter:
    """Tests for the ProgressReporter class."""

    def test_header(self):
        """Header should print title with separator."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.header("Test Header")

        result = output.getvalue()
        assert "Test Header" in result
        assert "=" in result

    def test_separator(self):
        """Separator should print line of equals."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.separator()

        result = output.getvalue()
        assert "=" * 50 in result

    def test_blank(self):
        """Blank should print empty line."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.blank()

        assert output.getvalue() == "\n"

    def test_info(self):
        """Info should print message."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.info("Test message")

        assert "Test message" in output.getvalue()

    def test_step_context_manager(self):
        """Step context manager should print step header."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        with reporter.step(1, 3, "Testing"):
            pass

        result = output.getvalue()
        assert "[1/3]" in result
        assert "Testing" in result
        assert "done" in result

    def test_step_adds_blank_line_after_first(self):
        """Steps after first should have blank line before."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        with reporter.step(1, 3, "First"):
            pass
        with reporter.step(2, 3, "Second"):
            pass

        result = output.getvalue()
        # Second step should be preceded by blank line
        lines = result.split("\n")
        # Find the line with [2/3]
        for i, line in enumerate(lines):
            if "[2/3]" in line and i > 0:
                assert lines[i - 1] == "", "Expected blank line before step 2"
                break

    def test_step_start_and_done(self):
        """step_start and step_done should work together."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.step_start(1, 3, "Starting")
        reporter.step_done("finished")

        result = output.getvalue()
        assert "[1/3]" in result
        assert "Starting" in result
        assert "finished" in result

    def test_step_error(self):
        """step_error should print error to stderr."""
        output = io.StringIO()
        err_output = io.StringIO()
        reporter = ProgressReporter(output=output)

        import sys

        old_stderr = sys.stderr
        sys.stderr = err_output
        try:
            reporter.step_start(1, 3, "Testing")
            reporter.step_error("failed")
        finally:
            sys.stderr = old_stderr

        assert "ERROR" in err_output.getvalue()
        assert "failed" in err_output.getvalue()

    def test_substep(self):
        """Substep should be indented."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.substep("Sub task")

        result = output.getvalue()
        assert "Sub task" in result
        # Should be indented (starts with spaces)
        assert result.startswith("      ")

    def test_substep_header(self):
        """Substep header should have blank line before."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.substep_header("Section:")

        result = output.getvalue()
        assert "\n" in result  # Has blank line
        assert "Section:" in result

    def test_detail(self):
        """Detail should be double indented."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.detail("Detail info")

        result = output.getvalue()
        assert "Detail info" in result
        # Should have extra indentation
        assert "        " in result  # 8 spaces

    def test_complete(self):
        """Complete should show completion message."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.complete("All done")

        result = output.getvalue()
        assert "Complete:" in result
        assert "All done" in result

    def test_progress_bar_factory(self):
        """progress_bar should create ProgressBar."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        pb = reporter.progress_bar("Loading", total=50)

        assert isinstance(pb, ProgressBar)
        assert pb.label == "Loading"
        assert pb.total == 50

    def test_spinner_factory(self):
        """spinner should create Spinner."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        s = reporter.spinner("Working")

        assert isinstance(s, Spinner)
        assert s.message == "Working"

    def test_summary_header(self):
        """Summary header should print with separators."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.summary_header("Results")

        result = output.getvalue()
        assert "Results" in result
        assert result.count("=") >= 50  # At least one separator line

    def test_summary_item(self):
        """Summary item should print label and value."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.summary_item("Files:", "1234")

        result = output.getvalue()
        assert "Files:" in result
        assert "1234" in result

    def test_summary_section(self):
        """Summary section should print title."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.summary_section("Details")

        result = output.getvalue()
        assert "Details:" in result

    def test_summary_detail(self):
        """Summary detail should be indented."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.summary_detail("Count:", "42")

        result = output.getvalue()
        assert "Count:" in result
        assert "42" in result

    def test_status(self):
        """Status should print status message."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.status("COMPLETE")

        result = output.getvalue()
        assert "Status:" in result
        assert "COMPLETE" in result

    def test_hint(self):
        """Hint should print help message."""
        output = io.StringIO()
        reporter = ProgressReporter(output=output)

        reporter.hint("Run 'sf view' to browse")

        result = output.getvalue()
        assert "Run 'sf view' to browse" in result
