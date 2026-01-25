"""
Orchestrator module for simplified SF export workflow.

This module coordinates the full export pipeline:
1. Authentication
2. File export (Attachments + ContentVersions)
3. CSV export for essential objects
4. Document index building
5. SQLite database building
6. Optional verification and retry
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from .progress import spinner

_logger = logging.getLogger(__name__)


def _progress_bar(current: int, total: int, width: int = 20) -> str:
    """Return a visual progress bar string like [████████░░░░░░░░░░░░] 40%."""
    if total == 0:
        return "[" + "░" * width + "]   0%"
    pct = (current * 100) // total
    filled = (current * width) // total
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:3d}%"


# Lightweight objects for CI testing - core financial data only
# Used when SF_E2E_LIGHT=true to keep exports small (~1-2GB)
ESSENTIAL_OBJECTS_LIGHT = [
    "Account",
    "Contact",
    "Opportunity",
    "c2g__codaInvoice__c",
    "c2g__codaInvoiceLineItem__c",
    "c2g__codaTransaction__c",
    "c2g__codaPurchaseInvoice__c",
    "User",
]

# Essential objects for finance users - covers CRM, Finance, and HR
ESSENTIAL_OBJECTS = [
    # Core CRM
    "Account",
    "Contact",
    "Opportunity",
    "OpportunityLineItem",
    "Quote",
    "QuoteLineItem",
    "Product2",
    "Pricebook2",
    "PricebookEntry",
    "Asset",
    "Lead",
    "Campaign",
    "Case",
    "Task",
    "Event",
    "User",
    "RecordType",
    # Custom CRM
    "Project__c",
    "Invoices__c",
    # FinancialForce / Certinia Core
    "fferpcore__Company__c",
    "fferpcore__BillingDocument__c",
    "fferpcore__BillingDocumentLineItem__c",
    # CODA Accounting
    "c2g__codaCompany__c",
    "c2g__codaInvoice__c",
    "c2g__codaInvoiceLineItem__c",
    "c2g__codaCreditNote__c",
    "c2g__codaCreditNoteLineItem__c",
    "c2g__codaPurchaseInvoice__c",
    "c2g__codaPurchaseInvoiceLineItem__c",
    "c2g__codaPurchaseCreditNote__c",
    "c2g__codaTransaction__c",
    "c2g__codaJournal__c",
    "c2g__codaJournalLineItem__c",
    # PSA / Projects
    "pse__Proj__c",
    "pse__Milestone__c",
    "pse__Assignment__c",
    "pse__Timecard__c",
    "pse__Timecard_Header__c",
    "pse__Expense__c",
    "pse__Expense_Report__c",
    # HR / Employment
    "Engineer__c",
    "JobApplication__c",
    "HR_Activity__c",
    "Salary_History__c",
]

# Objects to index files by (for linking documents to records)
FILE_INDEX_OBJECTS = [
    "Opportunity",
    "Account",
    "Project__c",
    "Invoices__c",
    "c2g__codaInvoice__c",
    "c2g__codaCreditNote__c",
    "c2g__codaPurchaseInvoice__c",
    "c2g__codaPurchaseCreditNote__c",
    "pse__Proj__c",
    "pse__Expense_Report__c",
    "Engineer__c",
]


@dataclass
class ExportProgress:
    """Tracks export progress for UI updates."""

    step: int
    total_steps: int
    message: str
    detail: str = ""
    success: bool = True


@dataclass
class ExportResult:
    """Final result of export operation."""

    success: bool
    export_path: Path
    files_exported: int
    files_missing: int
    objects_exported: int
    objects_failed: list[str]
    database_path: Path | None
    error: str | None = None


def get_default_export_path() -> Path:
    """Get the default export path for today."""
    today = date.today().isoformat()
    return Path(f"./exports/export-{today}")


def _print_step(step: int, total: int, message: str, end: str = "\n") -> None:
    """Print a step indicator."""
    print(f"[{step}/{total}] {message}", end=end, flush=True)


def _print_success(message: str = "") -> None:
    """Print success indicator."""
    if message:
        print(f" {message}")
    else:
        print(" done")


def _print_error(message: str) -> None:
    """Print error indicator."""
    print(f" ERROR: {message}", file=sys.stderr)


def _load_csv_rows(csv_path: Path) -> list[dict]:
    """Load rows from a CSV file."""
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_full_export(
    export_path: Path | None = None,
    retry: bool = False,
    progress_callback: Callable[[ExportProgress], None] | None = None,
    verbose: bool = False,
    light: bool = False,
    max_files: int | None = None,
) -> ExportResult:
    """
    Run the complete export pipeline.

    Args:
        export_path: Where to save exports (default: ./exports/export-YYYY-MM-DD)
        retry: Whether to retry failed file downloads
        progress_callback: Optional callback for progress updates
        verbose: Show detailed output
        light: Use lightweight object list for CI testing (faster, less data)
        max_files: Limit number of files to download (for CI testing)

    Returns:
        ExportResult with summary of what was exported
    """
    # Import here to avoid circular imports and allow graceful failure
    from .api import SalesforceAPI
    from .dumper import dump_object_to_csv
    from .files import dump_attachments, dump_content_versions
    from .viewer.db_builder import build_sqlite_from_export

    if export_path is None:
        export_path = get_default_export_path()

    export_path = Path(export_path).resolve()
    # Always show 6 steps - step 6 runs automatically if files are missing
    total_steps = 6

    # Track results
    files_exported = 0
    files_missing = 0
    objects_exported = 0
    objects_failed: list[str] = []
    database_path: Path | None = None

    def report_progress(step: int, message: str, detail: str = "") -> None:
        if progress_callback:
            progress_callback(ExportProgress(step, total_steps, message, detail))
        _print_step(step, total_steps, message, end="" if not detail else "\n")
        if detail and verbose:
            print(f"      {detail}")

    print()
    print("SF Data Export")
    print("=" * 50)
    print(f"Output: {export_path}")
    print()

    # Step 1: Authenticate
    report_progress(1, "Authenticating to Salesforce...")
    try:
        api = SalesforceAPI()
        api.connect()
        _print_success()
    except Exception as e:
        _print_error(str(e))
        error_msg = str(e)
        if "SF_CLIENT_ID" in error_msg or "SF_CLIENT_SECRET" in error_msg:
            print()
            print("Setup required: Create a .env file with your Salesforce credentials:")
            print()
            print("  SF_CLIENT_ID=your_connected_app_consumer_key")
            print("  SF_CLIENT_SECRET=your_connected_app_consumer_secret")
            print("  SF_USERNAME=your_salesforce_username")
            print("  SF_PASSWORD=your_password_and_security_token")
            print()
            print("See: https://github.com/ksteptoe/sfdump#setup")
            print()
        return ExportResult(
            success=False,
            export_path=export_path,
            files_exported=0,
            files_missing=0,
            objects_exported=0,
            objects_failed=[],
            database_path=None,
            error=f"Authentication failed: {e}",
        )

    # Create export directories
    export_path.mkdir(parents=True, exist_ok=True)
    csv_dir = export_path / "csv"
    csv_dir.mkdir(exist_ok=True)
    links_dir = export_path / "links"
    links_dir.mkdir(exist_ok=True)
    meta_dir = export_path / "meta"
    meta_dir.mkdir(exist_ok=True)

    # Step 2: Export files (Attachments + ContentVersions)
    report_progress(2, "Exporting files (Attachments + Documents)...")
    try:
        # IMPORTANT: Clear any leftover chunking env vars from previous runs
        # These can cause incomplete exports if not cleared
        if light:
            # In light mode, limit file downloads for CI testing
            file_limit = max_files or 50
            os.environ["SFDUMP_FILES_CHUNK_TOTAL"] = str(file_limit)
            os.environ["SFDUMP_FILES_CHUNK_INDEX"] = "1"
            print(f"\n      [Light mode: limiting to ~{file_limit} files per type]")
        else:
            # Clear any stale chunking env vars to ensure full export
            if os.environ.get("SFDUMP_FILES_CHUNK_TOTAL"):
                _logger.warning(
                    "Clearing stale SFDUMP_FILES_CHUNK_TOTAL=%s env var",
                    os.environ.get("SFDUMP_FILES_CHUNK_TOTAL"),
                )
            os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)
            os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)

        # dump_attachments and dump_content_versions query internally and return stats
        print()
        print("      Attachments (legacy):")
        att_stats = dump_attachments(api, str(export_path))
        att_count = att_stats.get("count", 0)

        print()
        print("      Documents (ContentVersion):")
        cv_stats = dump_content_versions(api, str(export_path))
        cv_count = cv_stats.get("count", 0)

        files_exported = att_count + cv_count
        print()
        print(f"      File export complete: {files_exported:,} total files indexed")

        # Clean up env vars
        if light:
            os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)
            os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)

    except Exception as e:
        _print_error(str(e))
        _logger.exception("File export failed")
        # Continue with CSV export even if files fail

    # Step 3: Export essential CSVs
    report_progress(3, "Exporting data (Accounts, Invoices, etc.)...")

    # Use lightweight list for CI testing
    objects_to_export = ESSENTIAL_OBJECTS_LIGHT if light else ESSENTIAL_OBJECTS
    total_objects = len(objects_to_export)
    last_pct = -1

    print(f" {total_objects} objects", flush=True)

    for i, obj_name in enumerate(objects_to_export):
        try:
            _logger.info(f"Exporting {obj_name}...")
            dump_object_to_csv(api, obj_name, str(csv_dir))
            objects_exported += 1
        except Exception as e:
            objects_failed.append(obj_name)
            _logger.debug(f"Failed to export {obj_name}: {e}")

        # Show progress bar every 5%
        pct = ((i + 1) * 100) // total_objects
        if pct >= last_pct + 5 or i == total_objects - 1:
            print(f"\r      {_progress_bar(i + 1, total_objects)}", end="", flush=True)
            last_pct = pct

    print()  # End the line
    print(f"      Complete: {objects_exported} exported", end="")
    if objects_failed:
        print(f", {len(objects_failed)} unavailable")
    else:
        print()

    # Step 4: Build document indexes
    step_num = 4
    report_progress(step_num, "Building document indexes...")
    print()  # Newline for spinner
    docs_missing_path = 0
    try:
        from .command_files import build_files_index

        # Build index for each object type
        with spinner("Building file indexes..."):
            for obj_name in FILE_INDEX_OBJECTS:
                try:
                    build_files_index(api, obj_name, str(export_path))
                except Exception:
                    pass  # Object may not have files

        # Build master documents index
        from .command_docs_index import _build_master_index

        with spinner("Building master index..."):
            _, docs_with_path, docs_missing_path = _build_master_index(export_path)
        print("      done")

        # Log missing files for debugging - Step 6 will attempt recovery
        if docs_missing_path > 0:
            _logger.info(
                "Index shows %d/%d documents missing local files - will attempt recovery",
                docs_missing_path,
                docs_with_path + docs_missing_path,
            )
    except Exception as e:
        _print_error(str(e))
        _logger.exception("Index building failed")

    # Step 5: Build SQLite database
    step_num = 5
    report_progress(step_num, "Building search database...")
    print()  # Newline for spinner
    try:
        database_path = meta_dir / "sfdata.db"
        with spinner("Creating SQLite database..."):
            build_sqlite_from_export(str(export_path), str(database_path))
        print("      done")
    except Exception as e:
        _print_error(str(e))
        _logger.exception("Database build failed")
        database_path = None

    # Step 6: Verify files and recover any missing
    # This step runs automatically - no flags needed
    # Skip in light mode since missing files are expected (CI testing)
    step_num = 6
    if light:
        report_progress(step_num, "Verification...")
        _print_success("skipped (light mode)")
    else:
        report_progress(step_num, "Checking files...")

        try:
            from .backfill import load_missing_from_index, run_backfill
            from .retry import (
                merge_recovered_into_metadata,
                retry_missing_attachments,
                retry_missing_content_versions,
            )
            from .verify import verify_attachments, verify_content_versions

            att_meta = links_dir / "attachments.csv"
            cv_meta = links_dir / "content_versions.csv"
            master_index = meta_dir / "master_documents_index.csv"
            recovered_any = False

            # Scan for missing files from all sources
            print()  # Newline for spinner
            missing_in_index = []
            missing_attachments = []
            missing_content_versions = []

            with spinner("Verifying downloaded files..."):
                # Check master index (comprehensive list)
                if master_index.exists():
                    missing_in_index = load_missing_from_index(master_index)

                # Check metadata CSVs (detailed file info for retry)
                if att_meta.exists():
                    verify_attachments(str(att_meta), str(export_path))
                    missing_csv = links_dir / "attachments_missing.csv"
                    if missing_csv.exists():
                        missing_attachments = _load_csv_rows(missing_csv)

                if cv_meta.exists():
                    verify_content_versions(str(cv_meta), str(export_path))
                    missing_csv = links_dir / "content_versions_missing.csv"
                    if missing_csv.exists():
                        missing_content_versions = _load_csv_rows(missing_csv)

            # Calculate totals (index is comprehensive, includes metadata missing)
            total_missing = len(missing_in_index)
            metadata_missing = len(missing_attachments) + len(missing_content_versions)

            if total_missing == 0 and metadata_missing == 0:
                _print_success("all files verified")
            else:
                # Use the larger count (index is usually more comprehensive)
                files_to_recover = max(total_missing, metadata_missing)
                print(f"      {files_to_recover:,} files to download")

                recovered_count = 0

                # First-pass: retry from metadata CSVs (has detailed info)
                # tqdm progress bars display inside retry functions
                if missing_attachments:
                    retry_missing_attachments(
                        api, missing_attachments, str(export_path), str(links_dir)
                    )
                    retry_csv = links_dir / "attachments_missing_retry.csv"
                    if retry_csv.exists():
                        count = merge_recovered_into_metadata(str(att_meta), str(retry_csv))
                        if count > 0:
                            recovered_any = True
                            recovered_count += count

                if missing_content_versions:
                    retry_missing_content_versions(
                        api, missing_content_versions, str(export_path), str(links_dir)
                    )
                    retry_csv = links_dir / "content_versions_missing_retry.csv"
                    if retry_csv.exists():
                        count = merge_recovered_into_metadata(str(cv_meta), str(retry_csv))
                        if count > 0:
                            recovered_any = True
                            recovered_count += count

                # Second-pass: backfill remaining from master index
                if missing_in_index:
                    # tqdm progress bar handles display
                    backfill_result = run_backfill(
                        api,
                        export_path,
                        show_progress=True,
                    )

                    if backfill_result.downloaded > 0 or backfill_result.skipped > 0:
                        recovered_any = True
                        recovered_count += backfill_result.downloaded

                # Rebuild index and database if anything was recovered
                if recovered_any:
                    from .command_docs_index import _build_master_index

                    with spinner("Finalizing database..."):
                        _, docs_with_path_final, docs_missing_final = _build_master_index(
                            export_path
                        )
                        database_path = meta_dir / "sfdata.db"
                        build_sqlite_from_export(str(export_path), str(database_path))

                    files_missing = docs_missing_final
                else:
                    files_missing = total_missing

                # Final status - confident and simple
                if files_missing == 0:
                    print(f"      Recovered {recovered_count} files - all complete")
                elif recovered_count > 0:
                    print(f"      Recovered {recovered_count} files")
                    _logger.info(
                        "%d files unavailable (may no longer exist in Salesforce)",
                        files_missing,
                    )
                else:
                    _logger.info(
                        "%d files unavailable (may no longer exist in Salesforce)",
                        files_missing,
                    )

        except Exception as e:
            _print_error(str(e))
            _logger.exception("Verification failed")

    # Build reconciliation summary from master index
    master_index = meta_dir / "master_documents_index.csv"
    total_expected = 0
    total_downloaded = 0
    total_missing = 0

    if master_index.exists():
        index_rows = _load_csv_rows(master_index)
        for row in index_rows:
            total_expected += 1
            if (row.get("local_path") or "").strip():
                total_downloaded += 1
            else:
                total_missing += 1

    # Print summary
    print()
    print("=" * 50)
    print("Export Summary")
    print("=" * 50)
    print()
    print(f"  Location:   {export_path}")
    print()

    # Reconciliation
    if total_expected > 0:
        pct_complete = (total_downloaded / total_expected) * 100
        print("  Files:")
        print(f"    Expected:   {total_expected:,}")
        print(f"    Downloaded: {total_downloaded:,}")
        if total_missing > 0:
            print(f"    Missing:    {total_missing:,}")
        print(f"    Complete:   {pct_complete:.1f}%")
        print()

        if pct_complete >= 100:
            print("  Status: COMPLETE - All files downloaded successfully")
        elif pct_complete >= 99:
            print(f"  Status: NEARLY COMPLETE - {total_missing:,} files could not be retrieved")
            print("          (These may have been deleted from Salesforce)")
        else:
            print(f"  Status: INCOMPLETE - {total_missing:,} files still missing")
            print("          Run 'sf dump' again to continue downloading")
    else:
        print(f"  Files:      {files_exported}")

    print(f"  Objects:    {objects_exported}")
    if database_path and database_path.exists():
        print(f"  Database:   {database_path}")
    print()
    print("To browse your data:")
    print("  sf view")
    print()

    return ExportResult(
        success=True,
        export_path=export_path,
        files_exported=files_exported,
        files_missing=files_missing,
        objects_exported=objects_exported,
        objects_failed=objects_failed,
        database_path=database_path,
    )


def find_latest_export(base_path: Path = Path("./exports")) -> Path | None:
    """Find the most recent export directory."""
    if not base_path.exists():
        return None

    # Look for export-YYYY-MM-DD directories
    exports = sorted(
        [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("export-")],
        key=lambda d: d.name,
        reverse=True,
    )

    return exports[0] if exports else None


def ensure_database(export_path: Path) -> Path:
    """Ensure the SQLite database exists, building if necessary."""
    from .viewer.db_builder import build_sqlite_from_export

    db_path = export_path / "meta" / "sfdata.db"

    if db_path.exists():
        return db_path

    print(f"Building database for {export_path}...")
    (export_path / "meta").mkdir(parents=True, exist_ok=True)
    build_sqlite_from_export(str(export_path), str(db_path))
    print(f"Database ready: {db_path}")

    return db_path


def launch_viewer(export_path: Path | None = None) -> None:
    """
    Launch the Streamlit viewer for an export.

    Args:
        export_path: Path to export directory (auto-detects if not provided)
    """
    import subprocess

    # Find export path if not provided
    if export_path is None:
        export_path = find_latest_export()
        if export_path is None:
            print("No export found. Run 'sf dump' first.")
            sys.exit(1)

    export_path = Path(export_path).resolve()

    if not export_path.exists():
        print(f"Export directory not found: {export_path}")
        sys.exit(1)

    # Ensure database exists
    db_path = ensure_database(export_path)

    print()
    print("SF Data Viewer")
    print("=" * 50)
    print(f"Export:   {export_path}")
    print(f"Database: {db_path}")
    print()
    print("Starting viewer... (press Ctrl+C to stop)")
    print()

    # Set environment variables for the viewer
    env = os.environ.copy()
    env["SFDUMP_DB_PATH"] = str(db_path)
    env["SFDUMP_EXPORT_ROOT"] = str(export_path)

    # Find the viewer app module
    viewer_app_path = Path(__file__).parent / "viewer_app"

    # Launch Streamlit with the db_viewer app
    db_viewer_path = viewer_app_path / "apps" / "db_viewer.py"

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(db_viewer_path)],
            env=env,
            check=True,
        )
    except KeyboardInterrupt:
        print("\nViewer stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Viewer failed: {e}")
        sys.exit(1)
