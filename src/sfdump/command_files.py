from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError
from .files import (
    dump_attachments,
    dump_content_versions,
    estimate_attachments,
    estimate_content_versions,
)
from .utils import ensure_dir

_logger = logging.getLogger(__name__)

# optional .env loader
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass

# For building human-readable indexes linking files to parent records.
# Default is 'Name', but some objects use different label fields.
INDEX_LABEL_FIELDS: dict[str, str] = {
    # key = SObject API name, value = field to use as label in the index
    "SalesforceInvoice": "InvoiceNumber",
    # Add more special cases here if needed, e.g.:
    # "ffps_po__PurchaseOrder__c": "Name__c",
}


def _chunk(seq: List[str], size: int) -> Iterable[List[str]]:
    """Yield fixed-size chunks from a list."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def build_files_index(
    api: SalesforceAPI,
    index_object: str,
    out_dir: str,
    include_content: bool = True,
    include_attachments: bool = True,
    max_batch_size: int = 200,
) -> None:
    """Build a CSV index linking one sObject type to its Attachments and Files.

    The CSV will be written to: <out_dir>/links/<index_object>_files_index.csv

    Columns:
        object_type, record_id, record_name,
        file_source, file_id, file_link_id, file_name, file_extension
    """
    object_name = index_object.strip()
    if not object_name:
        _logger.warning("No index object provided, skipping index generation.")
        return

    base = Path(out_dir)
    links_dir = base / "links"
    links_dir.mkdir(parents=True, exist_ok=True)
    csv_path = links_dir / f"{object_name}_files_index.csv"

    _logger.info("Building files index for %s into %s", object_name, csv_path)

    # Decide which field to use as the human-readable label.
    # Default is "Name", with overrides from INDEX_LABEL_FIELDS.
    label_field = INDEX_LABEL_FIELDS.get(object_name, "Name")

    # 1) Fetch all records of the given object (Id + label_field)
    soql_records = f"SELECT Id, {label_field} FROM {object_name}"
    records: Dict[str, str] = {}

    _logger.debug(
        "Querying %s records for indexing (%s as label): %s",
        object_name,
        label_field,
        soql_records,
    )

    # Assumes SalesforceAPI has an iter_query(soql: str) generator
    for rec in api.iter_query(soql_records):
        rec_id = rec.get("Id")
        if not rec_id:
            continue
        rec_name = rec.get(label_field) or ""
        records[rec_id] = rec_name

    if not records:
        _logger.warning("No %s records found; index will be empty.", object_name)
        return

    record_ids = list(records.keys())
    _logger.info("Found %d %s records to index.", len(record_ids), object_name)

    fieldnames = [
        "object_type",
        "record_id",
        "record_name",
        "file_source",
        "file_id",
        "file_link_id",
        "file_name",
        "file_extension",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # 2) Attachments: ParentId -> record
        if include_attachments:
            for batch in _chunk(record_ids, max_batch_size):
                ids_str = ",".join(f"'{i}'" for i in batch)
                soql_att = (
                    f"SELECT Id, Name, ParentId FROM Attachment " f"WHERE ParentId IN ({ids_str})"
                )
                _logger.debug("Indexing Attachments batch: %s", soql_att)

                for att in api.iter_query(soql_att):
                    parent_id = att.get("ParentId")
                    if not parent_id:
                        continue
                    rec_name = records.get(parent_id, "")
                    name = att.get("Name") or ""
                    ext = name.rsplit(".", 1)[-1] if "." in name else ""
                    writer.writerow(
                        {
                            "object_type": object_name,
                            "record_id": parent_id,
                            "record_name": rec_name,
                            "file_source": "Attachment",
                            "file_id": att.get("Id") or "",
                            "file_link_id": "",  # not applicable to legacy Attachment
                            "file_name": name,
                            "file_extension": ext,
                        }
                    )

        # 3) Files (ContentDocumentLink): LinkedEntityId -> record
        if include_content:
            for batch in _chunk(record_ids, max_batch_size):
                ids_str = ",".join(f"'{i}'" for i in batch)
                soql_links = (
                    "SELECT Id, ContentDocumentId, LinkedEntityId, "
                    "       ContentDocument.Title, ContentDocument.FileExtension "
                    "FROM ContentDocumentLink "
                    f"WHERE LinkedEntityId IN ({ids_str})"
                )
                _logger.debug("Indexing Files batch: %s", soql_links)

                for link in api.iter_query(soql_links):
                    linked_id = link.get("LinkedEntityId")
                    if not linked_id:
                        continue
                    rec_name = records.get(linked_id, "")

                    cdoc = link.get("ContentDocument") or {}
                    if not isinstance(cdoc, dict):
                        cdoc = {}

                    title = cdoc.get("Title", "")
                    ext = cdoc.get("FileExtension", "")

                    writer.writerow(
                        {
                            "object_type": object_name,
                            "record_id": linked_id,
                            "record_name": rec_name,
                            "file_source": "File",
                            "file_id": link.get("ContentDocumentId") or "",
                            "file_link_id": link.get("Id") or "",
                            "file_name": title,
                            "file_extension": ext,
                        }
                    )

    _logger.info("Files index written to %s", csv_path)


@click.command("files")
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output directory.",
)
@click.option("--no-content", is_flag=True, help="Skip ContentVersion downloads.")
@click.option("--no-attachments", is_flag=True, help="Skip legacy Attachment downloads.")
@click.option(
    "--content-where",
    help="Extra AND filter for ContentVersion (without WHERE).",
)
@click.option(
    "--attachments-where",
    help="WHERE clause for Attachment (without WHERE).",
)
@click.option(
    "--max-workers",
    type=int,
    default=8,
    show_default=True,
    help="Parallel download workers.",
)
@click.option(
    "--estimate-only",
    is_flag=True,
    help="Do not download anything; just estimate counts and total bytes.",
)
@click.option(
    "--index-by",
    "index_by",
    metavar="SOBJECT",
    multiple=True,  # 👈 allow repeated flags
    help=(
        "Also build CSV index(es) mapping SOBJECT records to their related "
        "Attachments and Files (e.g. Opportunity, Account). "
        "May be given multiple times."
    ),
)
@click.option(
    "--index-only",
    is_flag=True,
    help=("Only build index CSVs for --index-by objects; " "do not download or estimate files."),
)
def files_cmd(
    out_dir: str,
    no_content: bool,
    no_attachments: bool,
    content_where: str | None,
    attachments_where: str | None,
    max_workers: int,
    estimate_only: bool,
    index_by: tuple[str, ...],
    index_only: bool,
) -> None:
    """Download Salesforce files and/or build index CSVs.

    By default this downloads ContentVersion (latest) & legacy Attachment.
    Optionally, build CSV index(es) linking one or more sObjects (e.g. Opportunity)
    to their related Attachments and Files via --index-by.

    Modes:
      * default          → download + (optional) index
      * --estimate-only  → estimate sizes only, no downloads
      * --index-only     → index only, no downloads or estimates
    """
    if estimate_only and index_only:
        raise click.ClickException(
            "Cannot use --estimate-only and --index-only together. " "Choose one mode."
        )

    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        missing = ", ".join(e.missing)
        msg = (
            f"Missing Salesforce JWT credentials: {missing}\n\n"
            "Set these environment variables or create a .env file. "
            "Run `sfdump login --help` for details."
        )
        raise click.ClickException(msg) from e

    results: list[dict] = []

    # ── 1) Estimation / download ──────────────────────────────────────────────
    if estimate_only:
        # Estimation mode: no filesystem writes for file bodies.
        if not no_content:
            results.append(
                estimate_content_versions(
                    api,
                    where=content_where,
                )
            )
        if not no_attachments:
            results.append(
                estimate_attachments(
                    api,
                    where=attachments_where,
                )
            )

    elif not index_only:
        # Real download mode.
        ensure_dir(out_dir)
        try:
            if not no_content:
                results.append(
                    dump_content_versions(
                        api,
                        out_dir,
                        where=content_where,
                        max_workers=max_workers,
                    )
                )

            if not no_attachments:
                results.append(
                    dump_attachments(
                        api,
                        out_dir,
                        where=attachments_where,
                        max_workers=max_workers,
                    )
                )
        except KeyboardInterrupt as exc:
            # Graceful abort on Ctrl+C
            click.echo(
                f"\nAborted by user (Ctrl+C). Partial output may remain in: {out_dir}",
                err=True,
            )
            raise click.Abort() from exc

    # index_only: we deliberately skip both estimation and download.
    # build_files_index doesn't read file bodies, so we just go straight to indexing.

    # ── 2) Optional: build index CSVs mapping <index_by> records to Files/Attachments ─
    if index_by:
        _logger.info(
            "Building file indexes%s for: %s",
            " (index-only mode)" if index_only else "",
            ", ".join(index_by),
        )
        for obj in index_by:
            try:
                build_files_index(
                    api=api,
                    index_object=obj,
                    out_dir=out_dir,
                    include_content=not no_content,
                    include_attachments=not no_attachments,
                )
            except Exception as exc:  # pragma: no cover - defensive
                _logger.exception("Failed to build files index for %s: %s", obj, exc)
                raise click.ClickException(f"Failed to build files index for {obj}: {exc}") from exc

    if not results and not index_by:
        # If we didn't estimate, download, or index anything, bail out.
        raise click.ClickException(
            "Nothing to do: both ContentVersion and Attachment were disabled."
        )

    def _format_bytes(num: float) -> str:
        """Human-readable byte format, like du -h."""
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        value = num
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                return f"{value:,.1f} {unit}"
            value /= 1024.0
        return f"{value:,.1f} PB"

    # short human summary per kind
    def line(r: dict) -> str:
        bytes_val = int(r.get("bytes") or 0)
        human = _format_bytes(float(bytes_val))
        return f"{r['kind']}: {r['count']} files, {human} ({bytes_val:,.0f} bytes) → {r['root']}"

    total_files = 0
    total_bytes = 0

    for r in results:
        click.echo(line(r))
        total_files += int(r.get("count") or 0)
        total_bytes += int(r.get("bytes") or 0)

    # overall total
    if results:
        total_human = _format_bytes(float(total_bytes))
        click.echo(f"Total: {total_files} files, {total_human} ({total_bytes:,.0f} bytes)")

    # Metadata (including the new index) location hint
    if (not estimate_only and not index_only) or index_by:
        # - normal download: show hint
        # - index-only with index_by: show hint
        click.echo(f"Metadata CSVs are under: {os.path.join(out_dir, 'links')}")
