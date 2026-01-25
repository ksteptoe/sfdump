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

_logger = logging.getLogger(__name__)

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
        print("      Downloading Attachments...")
        att_stats = dump_attachments(api, str(export_path))
        att_count = att_stats.get("count", 0)

        print("      Downloading ContentVersions...")
        cv_stats = dump_content_versions(api, str(export_path))
        cv_count = cv_stats.get("count", 0)

        files_exported = att_count + cv_count
        _print_success(f"{files_exported} files")

        # Clean up env vars
        if light:
            os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)
            os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)

    except Exception as e:
        _print_error(str(e))
        _logger.exception("File export failed")
        # Continue with CSV export even if files fail

    # Step 3: Export essential CSVs
    report_progress(3, "Exporting data (Accounts, Opportunities, Invoices...)...")
    print()

    # Use lightweight list for CI testing
    objects_to_export = ESSENTIAL_OBJECTS_LIGHT if light else ESSENTIAL_OBJECTS

    for obj_name in objects_to_export:
        try:
            if verbose:
                print(f"      Exporting {obj_name}...")
            dump_object_to_csv(api, obj_name, str(csv_dir))
            objects_exported += 1
        except Exception as e:
            if verbose:
                print(f"      Skipping {obj_name}: {e}")
            objects_failed.append(obj_name)
            _logger.debug(f"Failed to export {obj_name}: {e}")

    print(f"      Exported {objects_exported} objects", end="")
    if objects_failed:
        print(f" ({len(objects_failed)} skipped)")
    else:
        print()

    # Step 4: Build document indexes
    step_num = 4
    report_progress(step_num, "Building document indexes...")
    docs_missing_path = 0
    try:
        from .command_files import build_files_index

        # Build index for each object type
        for obj_name in FILE_INDEX_OBJECTS:
            try:
                build_files_index(api, obj_name, str(export_path))
            except Exception:
                pass  # Object may not have files

        # Build master documents index
        from .command_docs_index import _build_master_index

        _, docs_with_path, docs_missing_path = _build_master_index(export_path)
        _print_success()

        # Warn if many documents are missing local files
        if docs_missing_path > 0:
            total = docs_with_path + docs_missing_path
            pct = (docs_missing_path / total) * 100 if total > 0 else 0
            print(
                f"      ⚠️  {docs_missing_path}/{total} indexed documents ({pct:.0f}%) "
                f"have no local file"
            )
            if pct > 10:
                print(
                    "      This may indicate an incomplete export. "
                    "Check if SFDUMP_FILES_CHUNK_* env vars were set."
                )
    except Exception as e:
        _print_error(str(e))
        _logger.exception("Index building failed")

    # Step 5: Build SQLite database
    step_num = 5
    report_progress(step_num, "Building search database...")
    try:
        database_path = meta_dir / "sfdata.db"
        build_sqlite_from_export(str(export_path), str(database_path))
        _print_success()
    except Exception as e:
        _print_error(str(e))
        _logger.exception("Database build failed")
        database_path = None

    # Step 6: Verify and retry missing files
    # Always run when missing docs detected OR when --retry flag is used
    # Skip in light mode since missing files are expected
    should_retry = retry or (docs_missing_path > 0 and not light)
    if not should_retry:
        step_num = 6
        report_progress(step_num, "Verification...")
        _print_success("all files present")

    if should_retry:
        step_num = 6
        if docs_missing_path > 0:
            report_progress(step_num, f"Recovering {docs_missing_path} missing files...")
        else:
            report_progress(step_num, "Verifying and retrying failed downloads...")

        try:
            from .retry import (
                merge_recovered_into_metadata,
                retry_missing_attachments,
                retry_missing_content_versions,
            )
            from .verify import verify_attachments, verify_content_versions

            att_meta = links_dir / "attachments.csv"
            cv_meta = links_dir / "content_versions.csv"
            recovered_any = False

            # Verify attachments
            if att_meta.exists():
                verify_attachments(str(att_meta), str(export_path))
                missing_att_csv = links_dir / "attachments_missing.csv"
                if missing_att_csv.exists():
                    missing_att = _load_csv_rows(missing_att_csv)
                    if missing_att:
                        print(f"\n      Retrying {len(missing_att)} missing attachments...")
                        retry_missing_attachments(
                            api, missing_att, str(export_path), str(links_dir)
                        )
                        # Merge recovered paths back into original metadata
                        retry_csv = links_dir / "attachments_missing_retry.csv"
                        if retry_csv.exists():
                            count = merge_recovered_into_metadata(
                                str(att_meta), str(retry_csv)
                            )
                            if count > 0:
                                recovered_any = True
                                print(f"      Merged {count} recovered attachment paths")

            # Verify content versions
            if cv_meta.exists():
                verify_content_versions(str(cv_meta), str(export_path))
                missing_cv_csv = links_dir / "content_versions_missing.csv"
                if missing_cv_csv.exists():
                    missing_cv = _load_csv_rows(missing_cv_csv)
                    if missing_cv:
                        print(f"      Retrying {len(missing_cv)} missing content versions...")
                        retry_missing_content_versions(
                            api, missing_cv, str(export_path), str(links_dir)
                        )
                        # Merge recovered paths back into original metadata
                        retry_csv = links_dir / "content_versions_missing_retry.csv"
                        if retry_csv.exists():
                            count = merge_recovered_into_metadata(
                                str(cv_meta), str(retry_csv)
                            )
                            if count > 0:
                                recovered_any = True
                                print(f"      Merged {count} recovered content version paths")

            # If files were recovered, rebuild index and database
            if recovered_any:
                print("      Rebuilding document index...")
                from .command_docs_index import _build_master_index

                _, docs_with_path_new, docs_missing_path_new = _build_master_index(export_path)

                print("      Rebuilding database...")
                database_path = meta_dir / "sfdata.db"
                build_sqlite_from_export(str(export_path), str(database_path))

                docs_missing_path = docs_missing_path_new

            # Re-verify to get final count
            files_missing = 0
            if att_meta.exists():
                verify_attachments(str(att_meta), str(export_path))
                missing_csv = links_dir / "attachments_missing.csv"
                if missing_csv.exists():
                    files_missing += len(_load_csv_rows(missing_csv))
            if cv_meta.exists():
                verify_content_versions(str(cv_meta), str(export_path))
                missing_csv = links_dir / "content_versions_missing.csv"
                if missing_csv.exists():
                    files_missing += len(_load_csv_rows(missing_csv))

            if files_missing == 0:
                _print_success("100% complete")
            else:
                print(f"      {files_missing} files still missing (may be deleted in Salesforce)")

            # Step 6b: Second-pass backfill from master_documents_index.csv
            # This recovers files not recorded in content_versions.csv due to chunking
            master_index = meta_dir / "master_documents_index.csv"
            if master_index.exists() and files_missing > 0:
                from .backfill import load_missing_from_index, run_backfill

                missing_in_index = load_missing_from_index(master_index)
                if missing_in_index:
                    print(f"\n      Second-pass recovery: {len(missing_in_index)} files...")

                    def show_backfill_progress(
                        processed: int, total: int, downloaded: int, failed: int
                    ) -> None:
                        pct = (processed / total) * 100 if total > 0 else 0
                        print(
                            f"      [{processed}/{total}] {pct:.0f}% - "
                            f"OK:{downloaded} Fail:{failed}"
                        )

                    backfill_result = run_backfill(
                        api,
                        export_path,
                        progress_callback=show_backfill_progress,
                        progress_interval=100,
                    )

                    if backfill_result.downloaded > 0:
                        recovered_any = True
                        print(
                            f"      Backfill complete: {backfill_result.downloaded} recovered, "
                            f"{backfill_result.failed} failed"
                        )

                        # Rebuild index and database
                        print("      Rebuilding document index...")
                        _, docs_with_path_new, docs_missing_path_new = _build_master_index(
                            export_path
                        )

                        print("      Rebuilding database...")
                        database_path = meta_dir / "sfdata.db"
                        build_sqlite_from_export(str(export_path), str(database_path))

                        docs_missing_path = docs_missing_path_new
                        files_missing = docs_missing_path_new

        except Exception as e:
            _print_error(str(e))
            _logger.exception("Verification failed")

    # Print summary
    print()
    print("=" * 50)
    print("Export complete!")
    print()
    print(f"  Location:  {export_path}")
    print(f"  Files:     {files_exported}")
    print(f"  Objects:   {objects_exported}")
    if database_path and database_path.exists():
        print(f"  Database:  {database_path}")
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
