from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import click

_logger = logging.getLogger(__name__)


def _ensure_meta_dir(export_root: Path) -> Path:
    meta = export_root / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    return meta


def _query(api: object, soql: str) -> List[Dict[str, Any]]:
    """
    Adapter over your SalesforceAPI wrapper.

    Tries common query methods. Update here if needed.
    """
    for meth_name in ("query_all", "query", "run_query"):
        if hasattr(api, meth_name):
            meth = getattr(api, meth_name)
            res = meth(soql)  # type: ignore[misc]
            # Normalise common response shapes
            if isinstance(res, dict) and "records" in res:
                return list(res.get("records") or [])
            if isinstance(res, list):
                return res
            # some wrappers return an object with .records
            if hasattr(res, "records"):
                return list(res.records)
            return list(res)  # type: ignore[arg-type]
    raise click.ClickException(
        "SalesforceAPI has no query method. Update _query() in command_docs_for.py."
    )


def _chunks(seq: Sequence[str], n: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), n):
        yield list(seq[i : i + n])


@click.command("docs-for")
@click.option(
    "--id",
    "record_id",
    required=True,
    help="Salesforce record Id (e.g. invoice/journal/opportunity Id).",
)
@click.option(
    "-r",
    "--export-root",
    "export_root",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Export root directory (we write into EXPORT_ROOT/meta/).",
)
def docs_for_cmd(record_id: str, export_root: Path) -> None:
    """List files/attachments related to a record Id and write meta/docs_for_<id>.csv."""
    from sfdump.api import SalesforceAPI, SFConfig

    export_root = export_root.resolve()
    meta_dir = _ensure_meta_dir(export_root)
    out_csv = meta_dir / f"docs_for_{record_id}.csv"

    cfg = SFConfig.from_env()
    api = SalesforceAPI(cfg)
    api.connect()

    rows: List[Dict[str, Any]] = []

    # --- Attachments ---------------------------------------------------------
    att = _query(
        api,
        "SELECT Id, ParentId, Name, ContentType, BodyLength "
        f"FROM Attachment WHERE ParentId = '{record_id}'",
    )
    for r in att:
        rows.append(
            {
                "source": "Attachment",
                "record_id": record_id,
                "link_id": "",
                "content_document_id": "",
                "content_version_id": "",
                "attachment_id": r.get("Id", ""),
                "title": r.get("Name", ""),
                "file_type": r.get("ContentType", ""),
                "size": r.get("BodyLength", ""),
                "share_type": "",
                "visibility": "",
            }
        )

    # --- ContentDocumentLink -------------------------------------------------
    links = _query(
        api,
        "SELECT Id, ContentDocumentId, LinkedEntityId, ShareType, Visibility "
        f"FROM ContentDocumentLink WHERE LinkedEntityId = '{record_id}'",
    )

    doc_ids = sorted(
        {str(r.get("ContentDocumentId") or "") for r in links if r.get("ContentDocumentId")}
    )
    doc_map: Dict[str, Dict[str, Any]] = {}
    ver_map: Dict[str, Dict[str, Any]] = {}

    if doc_ids:
        # ContentDocument IN clause needs quoting; keep chunks small
        for chunk in _chunks(doc_ids, 200):
            in_clause = ",".join(f"'{x}'" for x in chunk)
            docs = _query(
                api,
                "SELECT Id, Title, FileType, LatestPublishedVersionId "
                f"FROM ContentDocument WHERE Id IN ({in_clause})",
            )
            for d in docs:
                did = str(d.get("Id") or "")
                if did:
                    doc_map[did] = d

        # Latest ContentVersion for those documents
        for chunk in _chunks(doc_ids, 200):
            in_clause = ",".join(f"'{x}'" for x in chunk)
            vers = _query(
                api,
                "SELECT Id, ContentDocumentId, Title, VersionNumber, CreatedDate, "
                "FileExtension, ContentSize, IsLatest "
                f"FROM ContentVersion WHERE ContentDocumentId IN ({in_clause}) AND IsLatest = true",
            )
            for v in vers:
                did = str(v.get("ContentDocumentId") or "")
                if did:
                    ver_map[did] = v

    for link in links:
        did = str(link.get("ContentDocumentId") or "")
        doc = doc_map.get(did, {})

        ver = ver_map.get(did, {})

        rows.append(
            {
                "source": "File",
                "record_id": record_id,
                "link_id": link.get("Id", ""),
                "content_document_id": did,
                "content_version_id": ver.get("Id", "") or doc.get("LatestPublishedVersionId", ""),
                "attachment_id": "",
                "title": doc.get("Title", "") or ver.get("Title", ""),
                "file_type": doc.get("FileType", "") or ver.get("FileExtension", ""),
                "size": ver.get("ContentSize", ""),
                "share_type": link.get("ShareType", ""),
                "visibility": link.get("Visibility", ""),
            }
        )

    # --- Write ---------------------------------------------------------------
    fieldnames = [
        "source",
        "record_id",
        "link_id",
        "content_document_id",
        "content_version_id",
        "attachment_id",
        "title",
        "file_type",
        "size",
        "share_type",
        "visibility",
    ]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    click.echo(f"Wrote: {out_csv} ({len(rows)} rows)")
