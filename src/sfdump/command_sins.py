"""Bulk download invoice PDFs from Salesforce via Apex REST endpoint.

Reads the c2g__codaInvoice__c CSV export, filters by status, and downloads
each invoice as a PDF using the deployed SfdumpInvoicePdf Apex REST class.
Supports resume (skips existing non-empty PDFs) and parallel downloads.
"""

from __future__ import annotations

import csv
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import click
import requests

from .progress import CHECKMARK, ProgressReporter

_logger = logging.getLogger(__name__)

# Column names in the invoice CSV
COL_ID = "Id"
COL_NAME = "Name"
COL_STATUS = "c2g__InvoiceStatus__c"

# Apex REST endpoint path (deployed as SfdumpInvoicePdf)
APEX_REST_PATH = "/services/apexrest/sfdump/invoice-pdf"


@dataclass
class InvoiceRecord:
    id: str
    name: str  # SIN number, e.g. SIN001673
    status: str


@dataclass
class DownloadResult:
    invoice: InvoiceRecord
    success: bool
    size: int = 0
    error: str = ""
    skipped: bool = False


def read_invoices(csv_path: Path, status_filter: str = "Complete") -> list[InvoiceRecord]:
    """Read invoice records from CSV, filtering by status."""
    invoices: list[InvoiceRecord] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record_id = row.get(COL_ID, "").strip()
            name = row.get(COL_NAME, "").strip()
            status = row.get(COL_STATUS, "").strip()
            if not record_id or not name:
                continue
            if status_filter and status != status_filter:
                continue
            invoices.append(InvoiceRecord(id=record_id, name=name, status=status))
    return invoices


def _download_one(
    session: requests.Session,
    instance_url: str,
    invoice: InvoiceRecord,
    out_dir: Path,
    force: bool = False,
) -> DownloadResult:
    """Download a single invoice PDF. Returns a DownloadResult."""
    pdf_path = out_dir / f"{invoice.name}.pdf"

    # Skip if already downloaded (non-empty file) and not forcing
    if not force and pdf_path.exists() and pdf_path.stat().st_size > 0:
        return DownloadResult(
            invoice=invoice,
            success=True,
            size=pdf_path.stat().st_size,
            skipped=True,
        )

    url = f"{instance_url}{APEX_REST_PATH}?id={invoice.id}"
    try:
        resp = session.get(url, timeout=120)
        resp.raise_for_status()

        content = resp.content
        # Validate PDF content
        if not content.startswith(b"%PDF-"):
            return DownloadResult(
                invoice=invoice,
                success=False,
                error=f"Response is not a PDF ({len(content)} bytes, starts with {content[:20]!r})",
            )

        pdf_path.write_bytes(content)
        return DownloadResult(
            invoice=invoice,
            success=True,
            size=len(content),
        )
    except requests.RequestException as e:
        return DownloadResult(invoice=invoice, success=False, error=str(e))


def download_invoice_pdfs(
    csv_path: Path,
    out_dir: Path,
    token: str,
    instance_url: str,
    status_filter: str = "Complete",
    workers: int = 4,
    force: bool = False,
    reporter: ProgressReporter | None = None,
) -> tuple[int, int, int]:
    """Download all invoice PDFs matching the status filter.

    Returns (downloaded, skipped, failed) counts.
    """
    if reporter is None:
        reporter = ProgressReporter()

    # Step 1: Read invoices
    reporter.step_start(1, 3, "Reading invoice CSV")
    invoices = read_invoices(csv_path, status_filter)
    reporter.step_done(f"{len(invoices)} invoices ({status_filter})")

    if not invoices:
        reporter.info("No invoices to download.")
        return 0, 0, 0

    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 2: Check existing PDFs
    reporter.step_start(2, 3, "Checking existing PDFs")
    existing = 0
    if not force:
        for inv in invoices:
            pdf_path = out_dir / f"{inv.name}.pdf"
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                existing += 1
    to_download = len(invoices) - existing if not force else len(invoices)
    reporter.step_done(f"{existing} existing, {to_download} to download")

    if to_download == 0:
        reporter.blank()
        reporter.info("All invoices already downloaded. Use --force to re-download.")
        return 0, existing, 0

    # Step 3: Download PDFs
    reporter.step_start(3, 3, "Downloading invoice PDFs")
    reporter.blank()

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    downloaded = 0
    skipped = 0
    failed = 0
    failed_invoices: list[tuple[InvoiceRecord, str]] = []

    # Shared cancel flag for graceful shutdown
    cancel = threading.Event()

    with reporter.progress_bar("Downloading", total=len(invoices)) as pb:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_download_one, session, instance_url, inv, out_dir, force): inv
                for inv in invoices
            }
            done_count = 0
            try:
                for future in as_completed(futures):
                    if cancel.is_set():
                        break
                    result = future.result()
                    done_count += 1
                    pb.update(done_count)
                    if result.skipped:
                        skipped += 1
                    elif result.success:
                        downloaded += 1
                    else:
                        failed += 1
                        failed_invoices.append((result.invoice, result.error))
                        _logger.warning(
                            "Failed to download %s: %s",
                            result.invoice.name,
                            result.error,
                        )
            except KeyboardInterrupt:
                cancel.set()
                executor.shutdown(wait=False, cancel_futures=True)
                raise

    # Write metadata CSV
    _write_metadata(out_dir, invoices, failed_invoices)

    # Summary
    reporter.blank()
    reporter.info(f"  {CHECKMARK} Downloaded: {downloaded}")
    if skipped:
        reporter.info(f"  {CHECKMARK} Skipped (existing): {skipped}")
    if failed:
        reporter.info(f"  ! Failed: {failed}")
        for inv, err in failed_invoices[:5]:
            reporter.info(f"    - {inv.name}: {err}")
        if len(failed_invoices) > 5:
            reporter.info(f"    ... and {len(failed_invoices) - 5} more")

    return downloaded, skipped, failed


def _write_metadata(
    out_dir: Path,
    invoices: list[InvoiceRecord],
    failed: list[tuple[InvoiceRecord, str]],
) -> None:
    """Write a metadata CSV summarising the download results."""
    meta_path = out_dir / "invoice_pdfs_metadata.csv"
    failed_ids = {inv.id for inv, _ in failed}

    with open(meta_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["InvoiceId", "Name", "Status", "DownloadStatus", "FilePath"])
        for inv in invoices:
            pdf_path = out_dir / f"{inv.name}.pdf"
            if inv.id in failed_ids:
                dl_status = "failed"
                path_str = ""
            elif pdf_path.exists() and pdf_path.stat().st_size > 0:
                dl_status = "ok"
                path_str = str(pdf_path)
            else:
                dl_status = "missing"
                path_str = ""
            writer.writerow([inv.id, inv.name, inv.status, dl_status, path_str])


def build_invoice_pdf_index(
    csv_path: Path,
    invoices_dir: Path,
    export_root: Path,
    status_filter: str = "Complete",
) -> int:
    """Write a files_index CSV so the viewer shows invoice PDFs as documents.

    Creates links/c2g__codaInvoice__c_invoice_pdfs_files_index.csv.
    Every matching invoice gets an entry regardless of whether the PDF has
    been downloaded — the viewer will show it as "not available locally"
    until the PDF exists on disk.

    Returns number of index entries written.
    """
    invoices = read_invoices(csv_path, status_filter)
    if not invoices:
        return 0

    links_dir = export_root / "links"
    links_dir.mkdir(parents=True, exist_ok=True)

    index_path = links_dir / "c2g__codaInvoice__c_invoice_pdfs_files_index.csv"
    with open(index_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "object_type",
                "record_id",
                "record_name",
                "file_source",
                "file_id",
                "file_link_id",
                "file_name",
                "file_extension",
                "path",
                "content_type",
                "size_bytes",
            ]
        )
        for inv in invoices:
            pdf_path = invoices_dir / f"{inv.name}.pdf"
            rel_path = ""
            size = ""
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                try:
                    rel_path = pdf_path.relative_to(export_root).as_posix()
                except ValueError:
                    rel_path = str(pdf_path)
                size = str(pdf_path.stat().st_size)
            writer.writerow(
                [
                    "c2g__codaInvoice__c",
                    inv.id,
                    inv.name,
                    "InvoicePDF",
                    inv.id,
                    "",
                    f"{inv.name}.pdf",
                    "pdf",
                    rel_path,
                    "application/pdf",
                    size,
                ]
            )

    return len(invoices)


# ---------------------------------------------------------------------------
# Click command (for sfdump CLI)
# ---------------------------------------------------------------------------


@click.command("sins")
@click.option(
    "--csv",
    "csv_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to c2g__codaInvoice__c.csv. Auto-detected from latest export if omitted.",
)
@click.option(
    "--out",
    "out_dir",
    type=click.Path(path_type=Path),
    help="Output directory for PDFs (default: {export}/invoices/).",
)
@click.option(
    "--status",
    "status_filter",
    default="Complete",
    show_default=True,
    help="Invoice status to filter on.",
)
@click.option(
    "--workers",
    type=int,
    default=4,
    show_default=True,
    help="Number of parallel download workers.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-download existing PDFs.",
)
def sins_cmd(
    csv_path: Path | None,
    out_dir: Path | None,
    status_filter: str,
    workers: int,
    force: bool,
) -> None:
    """Download invoice PDFs from Salesforce.

    Reads the invoice CSV export and downloads each invoice as a PDF
    using the deployed Apex REST endpoint. Requires a web login session
    (run 'sfdump login-web' first).
    """
    from .orchestrator import find_latest_export
    from .sf_auth_web import get_instance_url, get_web_token

    reporter = ProgressReporter()
    reporter.header("Invoice PDF Download")

    # Resolve CSV path
    if csv_path is None:
        export_dir = find_latest_export()
        if export_dir is None:
            click.echo("No export found. Run 'sf dump' first.", err=True)
            raise SystemExit(1)
        csv_path = export_dir / "csv" / "c2g__codaInvoice__c.csv"
        if not csv_path.exists():
            click.echo(f"Invoice CSV not found: {csv_path}", err=True)
            raise SystemExit(1)

    # Resolve output directory
    if out_dir is None:
        out_dir = csv_path.parent.parent / "invoices"

    reporter.info(f"CSV:    {csv_path}")
    reporter.info(f"Output: {out_dir}")
    reporter.blank()

    # Get auth token
    try:
        token = get_web_token()
    except RuntimeError as e:
        click.echo(f"Auth error: {e}", err=True)
        click.echo("Run 'sfdump login-web' to authenticate.", err=True)
        raise SystemExit(1) from None

    instance_url = get_instance_url()

    # Resolve export root (parent of csv/ and invoices/)
    export_root = csv_path.parent.parent

    try:
        downloaded, skipped, failed = download_invoice_pdfs(
            csv_path=csv_path,
            out_dir=out_dir,
            token=token,
            instance_url=instance_url,
            status_filter=status_filter,
            workers=workers,
            force=force,
            reporter=reporter,
        )
    except KeyboardInterrupt:
        click.echo()
        click.echo("Download cancelled.")
        click.echo(f"Run 'sfdump sins --csv {csv_path}' to resume.")
        raise SystemExit(130) from None

    # Build viewer index so PDFs show up in the document panel
    indexed = build_invoice_pdf_index(csv_path, out_dir, export_root, status_filter)
    if indexed:
        reporter.blank()
        reporter.info(f"  Indexed {indexed} invoices for viewer")

    reporter.blank()
    if failed:
        reporter.info("Some downloads failed. Re-run to retry.")
        raise SystemExit(1)
    reporter.info("Done.")
