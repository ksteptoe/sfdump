"""
Orchestrator module for simplified SF export workflow.

This module coordinates the full export pipeline:
1. Authentication
2. File export (Attachments + ContentVersions)
3. CSV export for essential objects
4. Document index building
5. SQLite database building
6. Optional verification and retry

All UI output goes through the unified ProgressReporter for consistency.
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

from .exceptions import RateLimitError
from .progress import ProgressReporter

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

    # Create unified progress reporter - single source of truth for UI
    ui = ProgressReporter(verbose=verbose)

    if export_path is None:
        export_path = get_default_export_path()

    export_path = Path(export_path).resolve()
    total_steps = 7

    # Track results
    files_exported = 0
    files_missing = 0
    objects_exported = 0
    objects_failed: list[str] = []
    database_path: Path | None = None

    # Header
    ui.header("SF Data Export")
    ui.info(f"Output: {export_path}")

    # =========================================================================
    # Step 1: Authentication
    # =========================================================================
    ui.step_start(1, total_steps, "Authenticating to Salesforce")
    if progress_callback:
        progress_callback(ExportProgress(1, total_steps, "Authenticating"))

    try:
        with ui.spinner("Connecting"):
            api = SalesforceAPI()
            api.connect()
    except Exception as e:
        ui.step_error(str(e))
        error_msg = str(e)
        if "SF_CLIENT_ID" in error_msg or "SF_CLIENT_SECRET" in error_msg:
            ui.blank()
            ui.info("Setup required: Create a .env file with your Salesforce credentials:")
            ui.blank()
            ui.info("  SF_CLIENT_ID=your_connected_app_consumer_key")
            ui.info("  SF_CLIENT_SECRET=your_connected_app_consumer_secret")
            ui.info("  SF_USERNAME=your_salesforce_username")
            ui.info("  SF_PASSWORD=your_password_and_security_token")
            ui.blank()
            ui.info("See: https://github.com/ksteptoe/sfdump#setup")
            ui.blank()
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

    # =========================================================================
    # Step 2: Export files (Attachments + ContentVersions)
    # =========================================================================
    ui.step_start(2, total_steps, "Exporting files (Attachments + Documents)")
    if progress_callback:
        progress_callback(ExportProgress(2, total_steps, "Exporting files"))

    try:
        # Handle chunking env vars for light mode
        if light:
            file_limit = max_files or 50
            os.environ["SFDUMP_FILES_CHUNK_TOTAL"] = str(file_limit)
            os.environ["SFDUMP_FILES_CHUNK_INDEX"] = "1"
            ui.step_done(f"light mode (~{file_limit} files)")
        else:
            # Clear any stale chunking env vars
            if os.environ.get("SFDUMP_FILES_CHUNK_TOTAL"):
                _logger.warning(
                    "Clearing stale SFDUMP_FILES_CHUNK_TOTAL=%s env var",
                    os.environ.get("SFDUMP_FILES_CHUNK_TOTAL"),
                )
            os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)
            os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)
            ui.step_done()

        # Attachments (legacy)
        ui.substep_header("Attachments (legacy):")
        att_stats = dump_attachments(api, str(export_path))
        att_count = att_stats.get("count", 0)

        # Documents (ContentVersion)
        ui.substep_header("Documents (ContentVersion):")
        cv_stats = dump_content_versions(api, str(export_path))
        cv_count = cv_stats.get("count", 0)

        files_exported = att_count + cv_count
        ui.blank()
        ui.substep(f"File export complete: {files_exported:,} total files indexed")

        # Clean up env vars
        if light:
            os.environ.pop("SFDUMP_FILES_CHUNK_TOTAL", None)
            os.environ.pop("SFDUMP_FILES_CHUNK_INDEX", None)

    except RateLimitError:
        raise  # Re-raise to stop the export
    except Exception as e:
        ui.step_error(str(e))
        _logger.exception("File export failed")
        # Continue with CSV export even if files fail

    # =========================================================================
    # Step 3: Export essential CSVs
    # =========================================================================
    ui.step_start(3, total_steps, "Exporting object data to CSV files")
    if progress_callback:
        progress_callback(ExportProgress(3, total_steps, "Exporting CSVs"))

    objects_to_export = ESSENTIAL_OBJECTS_LIGHT if light else ESSENTIAL_OBJECTS
    total_objects = len(objects_to_export)
    ui.step_done(f"{total_objects} objects")

    with ui.progress_bar("Exporting", total=total_objects) as pb:
        for i, obj_name in enumerate(objects_to_export):
            try:
                _logger.info(f"Exporting {obj_name}...")
                dump_object_to_csv(api, obj_name, str(csv_dir))
                objects_exported += 1
            except RateLimitError:
                raise  # Re-raise to stop the export
            except Exception as e:
                objects_failed.append(obj_name)
                _logger.debug(f"Failed to export {obj_name}: {e}")
            pb.update(i + 1)

    if objects_failed:
        ui.complete(f"{objects_exported} CSV files exported, {len(objects_failed)} unavailable")
    else:
        ui.complete(f"{objects_exported} CSV files exported")

    # =========================================================================
    # Step 4: Build document indexes
    # =========================================================================
    ui.step_start(4, total_steps, "Building document indexes")
    if progress_callback:
        progress_callback(ExportProgress(4, total_steps, "Building indexes"))

    docs_missing_path = 0
    try:
        from .command_docs_index import _build_master_index
        from .command_files import build_files_index

        ui.step_done()

        with ui.spinner("Building file indexes"):
            for obj_name in FILE_INDEX_OBJECTS:
                try:
                    build_files_index(api, obj_name, str(export_path))
                except RateLimitError:
                    raise  # Re-raise to stop the export
                except Exception:
                    pass  # Object may not have files

        with ui.spinner("Building master index"):
            _, docs_with_path, docs_missing_path = _build_master_index(export_path)

        if docs_missing_path > 0:
            _logger.info(
                "Index shows %d/%d documents missing local files - will attempt recovery",
                docs_missing_path,
                docs_with_path + docs_missing_path,
            )
    except RateLimitError:
        raise  # Re-raise to stop the export
    except Exception as e:
        ui.step_error(str(e))
        _logger.exception("Index building failed")

    # =========================================================================
    # Step 5: Invoice PDFs
    # =========================================================================
    ui.step_start(5, total_steps, "Invoice PDFs")
    if progress_callback:
        progress_callback(ExportProgress(5, total_steps, "Invoice PDFs"))

    invoice_csv = csv_dir / "c2g__codaInvoice__c.csv"
    invoices_dir = export_path / "invoices"

    if not invoice_csv.exists():
        ui.step_done("no invoice CSV found, skipping")
    else:
        from .command_sins import build_invoice_pdf_index, download_invoice_pdfs

        # Check if PDFs already exist
        existing_pdfs = list(invoices_dir.glob("SIN*.pdf")) if invoices_dir.exists() else []

        if existing_pdfs:
            ui.step_done(f"{len(existing_pdfs)} PDFs found")
        else:
            # Try to download — requires web server OAuth token
            try:
                from .sf_auth_web import get_instance_url, get_web_token

                token = get_web_token()
                instance_url = get_instance_url()
                ui.step_done("downloading")
                try:
                    downloaded, skipped, failed = download_invoice_pdfs(
                        csv_path=invoice_csv,
                        out_dir=invoices_dir,
                        token=token,
                        instance_url=instance_url,
                        workers=4,
                        reporter=ui,
                    )
                    if failed:
                        ui.substep(
                            f"{downloaded} downloaded, {failed} failed (re-run 'sf sins' to retry)"
                        )
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    _logger.warning("Invoice PDF download failed: %s", e)
                    ui.substep(f"Download error: {e}")
                    ui.substep("Run 'sf sins' manually to download invoice PDFs")
            except Exception:
                ui.step_done("skipped (run 'sfdump login-web' then 'sf sins')")

        # Always build the viewer index (shows documents even if not yet downloaded)
        try:
            indexed = build_invoice_pdf_index(invoice_csv, invoices_dir, export_path)
            if indexed:
                ui.substep(f"Indexed {indexed} invoices for viewer")
        except Exception as e:
            _logger.warning("Failed to build invoice PDF index: %s", e)

    # =========================================================================
    # Step 6: Build SQLite database
    # =========================================================================
    ui.step_start(6, total_steps, "Building search database")
    if progress_callback:
        progress_callback(ExportProgress(6, total_steps, "Building database"))

    try:
        database_path = meta_dir / "sfdata.db"

        with ui.spinner("Creating SQLite database"):
            build_sqlite_from_export(str(export_path), str(database_path), overwrite=True)
    except RateLimitError:
        raise  # Re-raise to stop the export
    except Exception as e:
        ui.step_error(str(e))
        _logger.exception("Database build failed")
        database_path = None

    # =========================================================================
    # Step 7: Verify files and recover any missing
    # =========================================================================
    ui.step_start(7, total_steps, "Checking files")
    if progress_callback:
        progress_callback(ExportProgress(7, total_steps, "Verifying files"))

    if light:
        ui.step_done("skipped (light mode)")
    else:
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

            # Scan for missing files
            missing_in_index = []
            missing_attachments = []
            missing_content_versions = []

            with ui.spinner("Verifying downloaded files"):
                if master_index.exists():
                    missing_in_index = load_missing_from_index(master_index)

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

            total_missing = len(missing_in_index)
            metadata_missing = len(missing_attachments) + len(missing_content_versions)

            if total_missing == 0 and metadata_missing == 0:
                ui.substep("all files verified")
            else:
                files_to_recover = max(total_missing, metadata_missing)
                ui.substep(f"{files_to_recover:,} files to download")

                recovered_count = 0

                # First-pass: retry from metadata CSVs
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

                # Second-pass: backfill from master index
                if missing_in_index:
                    backfill_result = run_backfill(
                        api,
                        export_path,
                        show_progress=True,
                    )
                    if backfill_result.downloaded > 0 or backfill_result.skipped > 0:
                        recovered_any = True
                        recovered_count += backfill_result.downloaded

                # Rebuild database if anything was recovered
                # Note: Don't rebuild master index - backfill already updated it with
                # recovered paths. Rebuilding would overwrite those updates.
                if recovered_any:
                    with ui.spinner("Finalizing database"):
                        database_path = meta_dir / "sfdata.db"
                        build_sqlite_from_export(
                            str(export_path), str(database_path), overwrite=True
                        )

                    # Count actual missing from updated master index
                    if master_index.exists():
                        updated_rows = _load_csv_rows(master_index)
                        files_missing = sum(
                            1 for r in updated_rows if not (r.get("local_path") or "").strip()
                        )
                    else:
                        files_missing = 0
                else:
                    files_missing = total_missing

                # Final status
                if files_missing == 0:
                    ui.substep(f"Recovered {recovered_count} files - all complete")
                elif recovered_count > 0:
                    ui.substep(f"Recovered {recovered_count} files")
                    _logger.info(
                        "%d files unavailable (may no longer exist in Salesforce)",
                        files_missing,
                    )
                else:
                    _logger.info(
                        "%d files unavailable (may no longer exist in Salesforce)",
                        files_missing,
                    )

        except RateLimitError:
            raise  # Re-raise to stop the export
        except Exception as e:
            ui.step_error(str(e))
            _logger.exception("Verification failed")

    # =========================================================================
    # Summary
    # =========================================================================
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

    ui.summary_header("Export Summary")
    ui.summary_item("Location:", str(export_path))
    ui.blank()

    if total_expected > 0:
        pct_complete = (total_downloaded / total_expected) * 100
        ui.summary_section("Files")
        ui.summary_detail("Expected:", f"{total_expected:,}")
        ui.summary_detail("Downloaded:", f"{total_downloaded:,}")
        if total_missing > 0:
            ui.summary_detail("Missing:", f"{total_missing:,}")
        ui.summary_detail("Complete:", f"{pct_complete:.1f}%")
        ui.blank()

        if pct_complete >= 100:
            ui.status("COMPLETE - All files downloaded successfully")
        elif pct_complete >= 99:
            ui.status(f"NEARLY COMPLETE - {total_missing:,} files could not be retrieved")
            ui.hint("(These may have been deleted from Salesforce)")
        else:
            ui.status(f"INCOMPLETE - {total_missing:,} files still missing")
            ui.hint("Run 'sf dump' again to continue downloading")
    else:
        ui.summary_item("Files:", str(files_exported))

    # List the CSV files that were exported
    csv_files = sorted(csv_dir.glob("*.csv")) if csv_dir.exists() else []
    csv_names = [f.stem for f in csv_files]

    if csv_names:
        # Show count with examples
        examples = csv_names[:5]
        example_str = ", ".join(examples)
        if len(csv_names) > 5:
            example_str += ", ..."
        ui.summary_item("CSV Tables:", f"{objects_exported} ({example_str})")
        ui.hint("(Each table is a Salesforce object type exported to CSV)")
    else:
        ui.summary_item("CSV Tables:", str(objects_exported))

    if database_path and database_path.exists():
        ui.summary_item("Database:", str(database_path))
    ui.blank()
    ui.info("To browse your data:")
    ui.info("  sf view")
    ui.blank()

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

    if export_path is None:
        export_path = find_latest_export()
        if export_path is None:
            print("No export found. Run 'sf dump' first.")
            sys.exit(1)

    export_path = Path(export_path).resolve()

    if not export_path.exists():
        print(f"Export directory not found: {export_path}")
        sys.exit(1)

    db_path = ensure_database(export_path)

    print()
    print("SF Data Viewer")
    print("=" * 50)
    print(f"Export:   {export_path}")
    print(f"Database: {db_path}")
    print()
    print("Starting viewer... (press Ctrl+C to stop)")
    print()

    env = os.environ.copy()
    env["SFDUMP_DB_PATH"] = str(db_path)
    env["SFDUMP_EXPORT_ROOT"] = str(export_path)

    viewer_app_path = Path(__file__).parent / "viewer_app"
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
