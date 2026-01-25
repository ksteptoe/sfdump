"""
Progress and messaging utilities for consistent user feedback.

This module provides a unified way to display progress and status messages
throughout the export process, with support for different verbosity levels.

Verbosity levels:
- Default (no flags): Essential progress only - what step, final counts
- -v (INFO): Adds intermediate progress, timing, object-by-object status
- -vv (DEBUG): Full details including API calls, individual files
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, TextIO

_logger = logging.getLogger(__name__)

# Spinner characters for animated progress indicator
SPINNER_CHARS = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@contextmanager
def spinner(message: str = "", output: TextIO = sys.stdout) -> Iterator[None]:
    """
    Context manager that displays an animated spinner during long operations.

    Usage:
        with spinner("Processing"):
            do_long_operation()

    The spinner shows activity with a message like: "⠋ Processing..."
    When complete, it clears the line and the caller can print the result.
    """
    stop_event = threading.Event()
    spinner_thread = None

    def _spin() -> None:
        idx = 0
        while not stop_event.is_set():
            char = SPINNER_CHARS[idx % len(SPINNER_CHARS)]
            if message:
                print(f"\r{char} {message}", end="", flush=True, file=output)
            else:
                print(f"\r{char}", end="", flush=True, file=output)
            idx += 1
            stop_event.wait(0.1)  # Update every 100ms

    try:
        spinner_thread = threading.Thread(target=_spin, daemon=True)
        spinner_thread.start()
        yield
    finally:
        stop_event.set()
        if spinner_thread:
            spinner_thread.join(timeout=0.5)
        # Clear the spinner line
        print("\r" + " " * (len(message) + 10) + "\r", end="", flush=True, file=output)


@dataclass
class PhaseStats:
    """Statistics for a processing phase."""

    total: int = 0
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def succeeded(self) -> int:
        return self.processed - self.failed

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def summary(self) -> str:
        """Return a summary string."""
        parts = []
        if self.succeeded > 0:
            parts.append(f"{self.succeeded:,} downloaded")
        if self.skipped > 0:
            parts.append(f"{self.skipped:,} already had")
        if self.failed > 0:
            parts.append(f"{self.failed:,} failed")
        return ", ".join(parts) if parts else "none"


class ProgressReporter:
    """
    Unified progress reporting with consistent formatting.

    Usage:
        progress = ProgressReporter(verbose=True)
        progress.step(1, 6, "Authenticating...")
        progress.done()

        progress.step(2, 6, "Downloading files...")
        progress.phase_start("Attachments", 1500)
        progress.phase_update(100)  # processed 100
        progress.phase_complete()
    """

    def __init__(
        self,
        verbose: bool = False,
        debug: bool = False,
        output: TextIO = sys.stdout,
    ):
        self.verbose = verbose
        self.debug = debug
        self.output = output
        self._current_step = 0
        self._total_steps = 0
        self._phase_stats: PhaseStats | None = None
        self._phase_name = ""
        self._last_pct = -1

    def _print(self, msg: str, end: str = "\n", flush: bool = True) -> None:
        """Print to output stream."""
        print(msg, end=end, flush=flush, file=self.output)

    def _log_info(self, msg: str) -> None:
        """Log at INFO level (visible with -v)."""
        _logger.info(msg)

    def _log_debug(self, msg: str) -> None:
        """Log at DEBUG level (visible with -vv)."""
        _logger.debug(msg)

    # -------------------------------------------------------------------------
    # Step-level progress (the [1/6] [2/6] etc.)
    # -------------------------------------------------------------------------

    def step(self, num: int, total: int, message: str) -> None:
        """Start a new step."""
        self._current_step = num
        self._total_steps = total
        self._print(f"[{num}/{total}] {message}", end="")

    def done(self, message: str = "") -> None:
        """Mark current step as done."""
        if message:
            self._print(f" {message}")
        else:
            self._print(" done")

    def step_info(self, message: str) -> None:
        """Print info under current step (indented)."""
        self._print(f"      {message}")

    # -------------------------------------------------------------------------
    # Phase-level progress (within a step, e.g., "Attachments", "Documents")
    # -------------------------------------------------------------------------

    def phase_start(self, name: str, total: int, discovered_msg: str = "") -> PhaseStats:
        """
        Start a new phase within the current step.

        Args:
            name: Phase name (e.g., "Attachments", "Documents")
            total: Total items to process
            discovered_msg: Optional message about what was discovered

        Returns:
            PhaseStats object for tracking progress
        """
        self._phase_name = name
        self._phase_stats = PhaseStats(total=total)
        self._last_pct = -1

        if discovered_msg:
            self._print(f"      {discovered_msg}")

        self._log_info(f"Phase '{name}' starting: {total:,} items")
        return self._phase_stats

    def phase_checking(self, checked: int, total: int) -> None:
        """Update progress during the checking phase."""
        if total == 0:
            return
        pct = (checked * 100) // total
        if pct >= self._last_pct + 10:
            self._print(f" {pct}%", end="")
            self._last_pct = pct

    def phase_checked(self, existing: int, to_download: int) -> None:
        """Report results of checking phase."""
        self._print(" done")
        if self._phase_stats:
            self._phase_stats.skipped = existing

        if existing > 0 and to_download > 0:
            self._print(f"      {existing:,} already downloaded, {to_download:,} to download")
        elif existing > 0 and to_download == 0:
            self._print(f"      All {existing:,} already downloaded")
        elif to_download > 0:
            self._print(f"      Downloading {to_download:,}...")

    def phase_complete(self, downloaded: int = 0, failed: int = 0) -> None:
        """
        Complete the current phase with a summary.
        """
        if self._phase_stats:
            self._phase_stats.processed = downloaded + failed
            self._phase_stats.failed = failed

            # Only print summary if there was work to do
            if downloaded > 0 or failed > 0:
                elapsed = self._phase_stats.elapsed
                if failed == 0:
                    self._print(f"      Done: {downloaded:,} downloaded ({elapsed:.1f}s)")
                else:
                    self._print(
                        f"      Done: {downloaded:,} downloaded, {failed:,} failed ({elapsed:.1f}s)"
                    )

            self._log_info(
                f"Phase '{self._phase_name}' complete: "
                f"downloaded={downloaded}, skipped={self._phase_stats.skipped}, "
                f"failed={failed}, elapsed={self._phase_stats.elapsed:.1f}s"
            )

        self._phase_stats = None
        self._phase_name = ""

    # -------------------------------------------------------------------------
    # Object export progress (for Step 3)
    # -------------------------------------------------------------------------

    def objects_start(self, total: int) -> None:
        """Start object export phase."""
        self._phase_stats = PhaseStats(total=total)
        self._last_pct = -1
        if self.verbose:
            self._print(f"      Exporting {total} object types...")

    def object_progress(self, name: str, success: bool) -> None:
        """Report progress on a single object."""
        if self._phase_stats:
            self._phase_stats.processed += 1
            if not success:
                self._phase_stats.failed += 1

            # Show percentage progress
            pct = (self._phase_stats.processed * 100) // self._phase_stats.total
            if pct >= self._last_pct + 20 or self._phase_stats.processed == self._phase_stats.total:
                if not self.verbose:
                    self._print(f" {pct}%", end="")
                self._last_pct = pct

        if self.verbose:
            status = "ok" if success else "skipped"
            self._print(f"        {name}: {status}")

        self._log_debug(f"Object {name}: {'success' if success else 'failed'}")

    def objects_complete(self) -> None:
        """Complete object export phase."""
        if self._phase_stats:
            succeeded = self._phase_stats.succeeded
            failed = self._phase_stats.failed

            if not self.verbose:
                self._print("")  # End the percentage line

            self._print(f"      Done: {succeeded} objects exported", end="")
            if failed > 0:
                self._print(f" ({failed} unavailable)")
            else:
                self._print("")

            self._log_info(f"Object export complete: {succeeded} exported, {failed} unavailable")

        self._phase_stats = None

    # -------------------------------------------------------------------------
    # Summary output
    # -------------------------------------------------------------------------

    def summary_line(self, label: str, value: str) -> None:
        """Print a summary line."""
        self._print(f"  {label:<12} {value}")

    def blank_line(self) -> None:
        """Print a blank line."""
        self._print("")

    def separator(self, char: str = "=", width: int = 50) -> None:
        """Print a separator line."""
        self._print(char * width)

    def header(self, text: str) -> None:
        """Print a header."""
        self._print(text)
