"""
Unified progress reporting for consistent user feedback.

This module is the SINGLE SOURCE OF TRUTH for all UI output during exports.
All user-facing messages should go through the ProgressReporter class to ensure
consistent formatting and presentation.

Usage:
    from sfdump.progress import reporter

    reporter.header("SF Data Export")
    reporter.info(f"Output: {path}")

    with reporter.step(1, 6, "Authenticating to Salesforce"):
        api.connect()

    with reporter.step(2, 6, "Exporting files"):
        reporter.substep("Attachments (legacy):")
        with reporter.progress_bar("Checking", total=1000) as pb:
            for i, item in enumerate(items):
                process(item)
                pb.update(i + 1)
"""

from __future__ import annotations

import logging
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, TextIO

_logger = logging.getLogger(__name__)


def _supports_unicode() -> bool:
    """Check if the terminal supports Unicode output."""
    # Check if stdout encoding supports Unicode
    try:
        encoding = getattr(sys.stdout, "encoding", None) or ""
        if encoding.lower() in ("utf-8", "utf8", "utf-16", "utf-32"):
            return True
        # Try to encode a Unicode character
        "✓".encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


# Detect Unicode support once at module load
_UNICODE_SUPPORTED = _supports_unicode()

# Spinner characters for animated progress indicator
# Use ASCII fallback on terminals that don't support Unicode
if _UNICODE_SUPPORTED:
    SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    CHECKMARK = "✓"
    BAR_FILLED = "█"
    BAR_EMPTY = "░"
else:
    SPINNER_CHARS = "|/-\\"
    CHECKMARK = "+"
    BAR_FILLED = "#"
    BAR_EMPTY = "-"


class ProgressBar:
    """
    A progress bar with animated spinner that runs in a background thread.

    The spinner animates continuously (every 100ms) while the progress bar
    shows completion percentage. This provides visual feedback even when
    individual work items take several seconds.
    """

    def __init__(
        self,
        label: str = "",
        total: int = 100,
        width: int = 20,
        indent: str = "      ",
        output: TextIO = sys.stdout,
    ):
        self.label = label
        self.total = total
        self.width = width
        self.indent = indent
        self.output = output
        self._current = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _render_bar(self, spinner_idx: int) -> str:
        """Render the progress bar with current spinner character."""
        spinner_char = SPINNER_CHARS[spinner_idx % len(SPINNER_CHARS)]
        if self.total == 0:
            pct = 0
            filled = 0
        else:
            pct = (self._current * 100) // self.total
            filled = (self._current * self.width) // self.total
        bar = BAR_FILLED * filled + BAR_EMPTY * (self.width - filled)
        label_part = f"{self.label} " if self.label else ""
        return f"{self.indent}{label_part}{spinner_char} [{bar}] {pct:3d}%"

    def _animate(self) -> None:
        """Background thread that animates the spinner."""
        idx = 0
        while not self._stop_event.is_set():
            with self._lock:
                line = self._render_bar(idx)
            print(f"\r{line}", end="", flush=True, file=self.output)
            idx += 1
            self._stop_event.wait(0.1)  # Update every 100ms

    def update(self, current: int) -> None:
        """Update the progress value (thread-safe)."""
        with self._lock:
            self._current = current

    def __enter__(self) -> "ProgressBar":
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        # Print final state and newline
        with self._lock:
            line = self._render_bar(0)
        # Replace spinner with checkmark for final output
        line = line.replace(SPINNER_CHARS[0], CHECKMARK)
        print(f"\r{line}", flush=True, file=self.output)


class Spinner:
    """
    An animated spinner for operations without known progress.

    Shows activity with a spinning character and optional message.
    """

    def __init__(
        self,
        message: str = "",
        indent: str = "      ",
        output: TextIO = sys.stdout,
    ):
        self.message = message
        self.indent = indent
        self.output = output
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _animate(self) -> None:
        """Background thread that animates the spinner."""
        idx = 0
        while not self._stop_event.is_set():
            char = SPINNER_CHARS[idx % len(SPINNER_CHARS)]
            msg_part = f" {self.message}" if self.message else ""
            print(f"\r{self.indent}{char}{msg_part}", end="", flush=True, file=self.output)
            idx += 1
            self._stop_event.wait(0.1)

    def __enter__(self) -> "Spinner":
        # Print newline to ensure spinner is on its own line
        print(file=self.output)
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        # Show completion with checkmark (same pattern as ProgressBar)
        msg_part = f" {self.message}" if self.message else ""
        # Clear line and print final state with checkmark
        print(f"\r{self.indent}{CHECKMARK}{msg_part}", flush=True, file=self.output)


@dataclass
class StepContext:
    """Context for a step, used to track completion."""

    num: int
    total: int
    message: str
    reporter: "ProgressReporter"
    _completed: bool = False

    def done(self, message: str = "done") -> None:
        """Mark step as done with optional message."""
        if not self._completed:
            self.reporter._print(f" {message}")
            self._completed = True

    def error(self, message: str) -> None:
        """Mark step as failed with error message."""
        if not self._completed:
            self.reporter._print(f" ERROR: {message}", file=sys.stderr)
            self._completed = True


class ProgressReporter:
    """
    Unified progress reporting with consistent formatting.

    This class is the single source of truth for all user-facing output.
    It ensures consistent indentation, spacing, and formatting across
    all stages of the export process.

    Formatting conventions:
    - Major steps: [1/6] Message...
    - Substeps: 6-space indent
    - Progress bars: 6-space indent with animated spinner
    - Blank line between major steps
    """

    # Indentation constants
    INDENT = "      "  # 6 spaces for substeps
    SEPARATOR_WIDTH = 50
    SEPARATOR_CHAR = "="

    def __init__(
        self,
        output: TextIO = sys.stdout,
        verbose: bool = False,
    ):
        self.output = output
        self.verbose = verbose
        self._current_step = 0
        self._total_steps = 0

    def _print(self, msg: str = "", end: str = "\n", file: TextIO | None = None) -> None:
        """Print to output stream."""
        target = file or self.output
        print(msg, end=end, flush=True, file=target)

    # -------------------------------------------------------------------------
    # Headers and separators
    # -------------------------------------------------------------------------

    def header(self, text: str) -> None:
        """Print a header (e.g., 'SF Data Export')."""
        self._print()
        self._print(text)
        self._print(self.SEPARATOR_CHAR * self.SEPARATOR_WIDTH)

    def separator(self) -> None:
        """Print a separator line."""
        self._print(self.SEPARATOR_CHAR * self.SEPARATOR_WIDTH)

    def blank(self) -> None:
        """Print a blank line."""
        self._print()

    def info(self, message: str) -> None:
        """Print an info message (not indented)."""
        self._print(message)

    # -------------------------------------------------------------------------
    # Step-level progress ([1/6], [2/6], etc.)
    # -------------------------------------------------------------------------

    @contextmanager
    def step(self, num: int, total: int, message: str) -> Iterator[StepContext]:
        """
        Context manager for a major step.

        Usage:
            with reporter.step(1, 6, "Authenticating to Salesforce") as s:
                api.connect()
                s.done()  # or let it auto-complete

        Automatically adds blank line before step (except first) and
        prints step header.
        """
        self._current_step = num
        self._total_steps = total

        # Blank line before each step (for visual separation)
        if num > 1:
            self._print()

        self._print(f"[{num}/{total}] {message}...", end="")

        ctx = StepContext(num=num, total=total, message=message, reporter=self)
        try:
            yield ctx
        finally:
            # Auto-complete if not already done
            if not ctx._completed:
                ctx.done()

    def step_start(self, num: int, total: int, message: str) -> None:
        """
        Start a step without context manager (for complex flows).

        Use step_done() or step_error() to complete.
        """
        self._current_step = num
        self._total_steps = total

        if num > 1:
            self._print()

        self._print(f"[{num}/{total}] {message}...", end="")

    def step_done(self, message: str = "done") -> None:
        """Complete a step started with step_start()."""
        self._print(f" {message}")

    def step_error(self, message: str) -> None:
        """Mark a step as failed."""
        self._print(f" ERROR: {message}", file=sys.stderr)

    # -------------------------------------------------------------------------
    # Substep output (indented under current step)
    # -------------------------------------------------------------------------

    def substep(self, message: str) -> None:
        """Print a substep message (indented)."""
        self._print(f"{self.INDENT}{message}")

    def substep_header(self, message: str) -> None:
        """Print a substep header (e.g., 'Attachments (legacy):')."""
        self._print()  # Blank line before substep header
        self._print(f"{self.INDENT}{message}")

    def detail(self, message: str) -> None:
        """Print a detail message (double indented)."""
        self._print(f"{self.INDENT}  {message}")

    def complete(self, message: str) -> None:
        """Print a completion message for a substep."""
        self._print(f"{self.INDENT}Complete: {message}")

    # -------------------------------------------------------------------------
    # Progress indicators
    # -------------------------------------------------------------------------

    def progress_bar(
        self,
        label: str = "",
        total: int = 100,
        indent: str | None = None,
    ) -> ProgressBar:
        """
        Create an animated progress bar.

        Usage:
            with reporter.progress_bar("Exporting", total=44) as pb:
                for i, item in enumerate(items):
                    process(item)
                    pb.update(i + 1)
        """
        return ProgressBar(
            label=label,
            total=total,
            indent=indent or self.INDENT,
            output=self.output,
        )

    def spinner(self, message: str = "", indent: str | None = None) -> Spinner:
        """
        Create an animated spinner for unknown-duration operations.

        Usage:
            with reporter.spinner("Building indexes"):
                build_indexes()
        """
        return Spinner(
            message=message,
            indent=indent or self.INDENT,
            output=self.output,
        )

    # -------------------------------------------------------------------------
    # Summary output
    # -------------------------------------------------------------------------

    def summary_header(self, title: str = "Export Summary") -> None:
        """Print a summary section header."""
        self._print()
        self._print(self.SEPARATOR_CHAR * self.SEPARATOR_WIDTH)
        self._print(title)
        self._print(self.SEPARATOR_CHAR * self.SEPARATOR_WIDTH)
        self._print()

    def summary_item(self, label: str, value: str) -> None:
        """Print a summary item (label: value)."""
        self._print(f"  {label:<12} {value}")

    def summary_section(self, title: str) -> None:
        """Print a summary section title."""
        self._print(f"  {title}:")

    def summary_detail(self, label: str, value: str) -> None:
        """Print a summary detail (indented under section)."""
        self._print(f"    {label:<12} {value}")

    def status(self, message: str) -> None:
        """Print a status message."""
        self._print(f"  Status: {message}")

    def hint(self, message: str) -> None:
        """Print a hint/help message."""
        self._print(f"  {message}")


# Global reporter instance for convenience
# This can be replaced with a custom instance if needed
reporter = ProgressReporter()


# Legacy compatibility - keep the standalone spinner function
@contextmanager
def spinner(message: str = "", output: TextIO = sys.stdout) -> Iterator[None]:
    """
    Legacy context manager for spinner.

    Prefer using reporter.spinner() for new code.
    """
    s = Spinner(message=message, indent="", output=output)
    with s:
        yield
