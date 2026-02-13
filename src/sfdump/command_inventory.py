"""CLI command for export inventory / completeness check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .inventory import (
    CategoryStatus,
    FileCategory,
    InventoryManager,
    InventoryResult,
    _result_to_dict,
)
from .progress import ProgressReporter


def _status_label(status: CategoryStatus) -> str:
    """Format a status for display."""
    return status.value


def _fmt_count(n: int) -> str:
    """Format a number with thousands separator."""
    return f"{n:,}"


def _file_row_notes(cat: FileCategory) -> str:
    """Build inline notes for a file-category row."""
    downloaded = cat.expected - cat.missing
    parts: list[str] = []
    if cat.missing > 0:
        parts.append(f"{_fmt_count(cat.missing)} missing")
    if cat.actual != downloaded and cat.status != CategoryStatus.NOT_CHECKED:
        parts.append(f"{_fmt_count(cat.actual)} on disk")
    if not parts:
        return ""
    return "  (" + " · ".join(parts) + ")"


def _print_table(result: InventoryResult, ui: ProgressReporter) -> None:
    """Print the summary table."""
    ui.header("Export Inventory")
    ui.info(f"Location:  {result.export_root}")
    ui.blank()

    # Table header
    ui.info(f"  {'Category':<20} {'Status':<14} {'Tracked':>10}  {'Downloaded':>10}")
    ui.info(f"  {'─' * 20} {'─' * 14} {'─' * 10}  {'─' * 10}")

    # CSV Objects
    c = result.csv_objects
    ui.info(
        f"  {'CSV Objects':<20} {_status_label(c.status):<14}"
        f" {_fmt_count(c.expected_count):>10}  {_fmt_count(c.found_count):>10}"
    )

    # Attachments — show verified-present count (tracked - missing)
    a = result.attachments
    a_downloaded = a.expected - a.missing
    ui.info(
        f"  {'Attachments':<20} {_status_label(a.status):<14}"
        f" {_fmt_count(a.expected):>10}  {_fmt_count(a_downloaded):>10}"
        f"{_file_row_notes(a)}"
    )

    # ContentVersions — show verified-present count (tracked - missing)
    cv = result.content_versions
    cv_downloaded = cv.expected - cv.missing
    ui.info(
        f"  {'ContentVersions':<20} {_status_label(cv.status):<14}"
        f" {_fmt_count(cv.expected):>10}  {_fmt_count(cv_downloaded):>10}"
        f"{_file_row_notes(cv)}"
    )

    # Invoice PDFs
    inv = result.invoices
    extra = ""
    if inv.status == CategoryStatus.INCOMPLETE:
        extra = f"  ({_fmt_count(inv.missing)} missing)"
    ui.info(
        f"  {'Invoice PDFs':<20} {_status_label(inv.status):<14}"
        f" {_fmt_count(inv.expected):>10}  {_fmt_count(inv.actual):>10}{extra}"
    )

    # Indexes
    ix = result.indexes
    ui.info(
        f"  {'Indexes':<20} {_status_label(ix.status):<14}"
        f" {_fmt_count(ix.files_index_count):>10}  {_fmt_count(ix.files_index_count):>10}"
    )

    # Database
    db = result.database
    ui.info(
        f"  {'Database':<20} {_status_label(db.status):<14}"
        f" {'':>10}  {_fmt_count(db.table_count) + ' tables':>10}"
    )

    ui.blank()

    # Legend
    ui.info("  Tracked = records in metadata CSVs")
    ui.info("  Downloaded = verified present (Tracked minus Missing)")

    ui.blank()
    ui.info(f"  Overall: {_status_label(result.overall_status)}")

    if result.warnings:
        ui.blank()
        ui.info("  Actions needed:")
        for w in result.warnings:
            ui.info(f"    - {w}")


# ---------------------------------------------------------------------------
# Click command (sfdump inventory)
# ---------------------------------------------------------------------------


@click.command("inventory")
@click.option(
    "--export-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Export directory to check. Auto-detects latest if omitted.",
)
@click.option(
    "--json-only",
    is_flag=True,
    default=False,
    help="Output raw JSON to stdout (for scripting).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Show extra detail (missing objects, file lists).",
)
def inventory_cmd(
    export_root: Path | None,
    json_only: bool,
    verbose: bool,
) -> None:
    """Check completeness of an export.

    Inspects local files only (no Salesforce API calls) and reports
    per-category status: CSV objects, Attachments, ContentVersions,
    Invoice PDFs, Indexes, and Database.
    """
    from .orchestrator import find_latest_export

    # Resolve export root
    if export_root is None:
        export_root = find_latest_export()
        if export_root is None:
            click.echo("No export found. Run 'sf dump' first.", err=True)
            raise SystemExit(1)

    manager = InventoryManager(export_root)
    result = manager.run()

    # Build warnings
    if result.csv_objects.missing_objects:
        result.warnings.append(
            f"CSV: {len(result.csv_objects.missing_objects)} expected objects not exported"
        )
    if result.content_versions.missing > 0:
        result.warnings.append(
            f"ContentVersions: {result.content_versions.missing} not yet downloaded"
            " — run: sfdump retry-missing"
        )
    if result.attachments.missing > 0:
        result.warnings.append(
            f"Attachments: {result.attachments.missing} not yet downloaded"
            " — run: sfdump retry-missing"
        )
    if result.invoices.status == CategoryStatus.INCOMPLETE:
        result.warnings.append(f"Invoice PDFs: {result.invoices.missing} not yet downloaded")
    if result.indexes.master_rows_missing_path > 0:
        result.warnings.append(
            f"Master index: {result.indexes.master_rows_missing_path} documents "
            "without local file path"
        )

    # Write manifest
    manifest_path = manager.write_manifest(result)

    if json_only:
        data = _result_to_dict(result)
        json.dump(data, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return

    ui = ProgressReporter(verbose=verbose)
    _print_table(result, ui)

    if verbose and result.csv_objects.missing_objects:
        ui.blank()
        ui.info("  Missing CSV objects:")
        for obj in result.csv_objects.missing_objects:
            ui.info(f"    - {obj}")

    if verbose and result.csv_objects.extra_objects:
        ui.blank()
        ui.info("  Extra CSV objects (not in ESSENTIAL_OBJECTS):")
        for obj in result.csv_objects.extra_objects:
            ui.info(f"    - {obj}")

    ui.blank()
    ui.info(f"  Manifest saved: {manifest_path}")
    ui.info(f"  Completed in {result.duration_seconds}s")
    ui.blank()
