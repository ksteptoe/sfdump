from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError
from .files import dump_attachments, dump_content_versions
from .manifest import Manifest, scan_files, scan_objects
from .manifest import write_manifest as write_manifest_file
from .utils import ensure_dir

_logger = logging.getLogger(__name__)


# -----------------------------
# Small utilities
# -----------------------------
def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _links_dir_for_out(out_dir: str) -> Path:
    # must match command_files canonical location
    return Path(out_dir) / "files" / "links"


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def _write_csv(
    path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    if fieldnames is None:
        keys = set()
        for r in rows:
            keys |= set(r.keys())
        fieldnames = sorted(keys)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _chunk(seq: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _try_query_all(api: SalesforceAPI, soql: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Resilient query wrapper:
      - returns (rows, None) on success
      - returns ([], "Type: message") on any exception
    """
    try:
        return list(api.query_all_iter(soql)), None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


# -----------------------------
# Command
# -----------------------------
@click.command("probe")
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output directory (same as 'files' and 'manifest').",
)
@click.option(
    "--no-download", is_flag=True, help="Skip ContentVersion/Attachment downloads; probes only."
)
@click.option(
    "--no-content", is_flag=True, help="Skip ContentVersion downloads (if downloads are enabled)."
)
@click.option(
    "--no-attachments",
    is_flag=True,
    help="Skip legacy Attachment downloads (if downloads are enabled).",
)
@click.option("--content-where", help="Extra AND filter for ContentVersion (without WHERE).")
@click.option("--attachments-where", help="WHERE clause for Attachment (without WHERE).")
@click.option(
    "--max-workers",
    type=int,
    default=8,
    show_default=True,
    help="Parallel download workers (if downloads are enabled).",
)
@click.option(
    "--email-bodies/--no-email-bodies",
    default=True,
    show_default=True,
    help="Include EmailMessage HtmlBody/TextBody in probe export (can be large).",
)
@click.option(
    "--write-manifest/--no-write-manifest",
    default=True,
    show_default=True,
    help="Write manifest.json after probe (recommended).",
)
def probe_cmd(
    out_dir: str,
    no_download: bool,
    no_content: bool,
    no_attachments: bool,
    content_where: str | None,
    attachments_where: str | None,
    max_workers: int,
    email_bodies: bool,
    write_manifest: bool,
) -> None:
    """
    Org-wide “odd-angle” probe that complements `files`.

    Important Salesforce restriction:
      ContentDocumentLink cannot be queried without filtering by either:
        - ContentDocumentId = '...'
        - LinkedEntityId = '...'
      or IN(...) variants.
    So we *seed* ContentDocumentLink queries using ContentDocumentIds from ContentVersion.

    Outputs:
      <out>/meta/probe_report.json
      <out>/meta/global_describe.json
      <out>/files/links/probe_*.jsonl
      <out>/files/links/probe_*.csv
    """
    ensure_dir(out_dir)

    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        missing = ", ".join(e.missing)
        raise click.ClickException(
            f"Missing Salesforce credentials: {missing}\nSet env vars or .env and re-run."
        ) from e

    meta_dir = Path(out_dir) / "meta"
    links_dir = _links_dir_for_out(out_dir)
    meta_dir.mkdir(parents=True, exist_ok=True)
    links_dir.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "generated_utc": _utc_now(),
        "out_dir": str(Path(out_dir).resolve()),
        "whoami": {},
        "counts": {},
        "errors": {},
        "notes": [],
    }

    # --- identity snapshot
    try:
        report["whoami"] = api.whoami()
    except Exception as e:
        report["errors"]["whoami"] = f"{type(e).__name__}: {e}"

    # --- global describe snapshot (what we can see)
    _logger.info("Probe: global describe…")
    gd = api.describe_global()
    _write_json(meta_dir / "global_describe.json", gd)
    sobjects = gd.get("sobjects", []) or []
    report["counts"]["sobjects_total"] = len(sobjects)
    report["counts"]["sobjects_queryable"] = sum(1 for o in sobjects if o.get("queryable") is True)

    # ------------------------------------------------------------
    # Optional: heavy downloads using your proven pipeline
    # ------------------------------------------------------------
    if not no_download:
        if not no_content:
            _logger.info("Downloading ContentVersion via existing pipeline…")
            try:
                dump_content_versions(api, out_dir, where=content_where, max_workers=max_workers)
            except Exception as e:
                report["errors"]["dump_content_versions"] = f"{type(e).__name__}: {e}"
        if not no_attachments:
            _logger.info("Downloading Attachment via existing pipeline…")
            try:
                dump_attachments(api, out_dir, where=attachments_where, max_workers=max_workers)
            except Exception as e:
                report["errors"]["dump_attachments"] = f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------
    # Probes: “odd angles”
    # ------------------------------------------------------------

    # 1) Latest ContentVersion list (seed set + reconciliation)
    _logger.info("Probe: ContentVersion (IsLatest=true)…")
    cv_rows, err = _try_query_all(
        api,
        "SELECT Id, ContentDocumentId, Title, FileExtension, FileType, ContentSize, "
        "CreatedDate, LastModifiedDate "
        "FROM ContentVersion WHERE IsLatest = true",
    )
    if err:
        report["errors"]["ContentVersion_latest"] = err
    report["counts"]["ContentVersion_latest"] = len(cv_rows)
    _write_jsonl(links_dir / "probe_content_versions_latest.jsonl", cv_rows)

    doc_ids = sorted({r.get("ContentDocumentId") for r in cv_rows if r.get("ContentDocumentId")})
    report["counts"]["ContentVersion_unique_ContentDocumentId"] = len(doc_ids)

    # 2) ContentDocumentLink seeded by ContentDocumentId IN (...)
    # (works around the org restriction that forbids unfiltered CDL queries)
    cdl_seeded: List[Dict[str, Any]] = []
    if doc_ids:
        _logger.info("Probe: ContentDocumentLink seeded by ContentDocumentId (IN batches)…")
        for chunk in _chunk(doc_ids, 500):
            in_list = ",".join(f"'{x}'" for x in chunk)
            rows, e = _try_query_all(
                api,
                "SELECT Id, ContentDocumentId, LinkedEntityId, ShareType, Visibility, SystemModstamp "
                f"FROM ContentDocumentLink WHERE ContentDocumentId IN ({in_list})",
            )
            if e:
                report.setdefault("errors", {}).setdefault("ContentDocumentLink_seeded", []).append(
                    e
                )
            cdl_seeded.extend(rows)

    report["counts"]["ContentDocumentLink_seeded"] = len(cdl_seeded)
    _write_jsonl(links_dir / "probe_content_document_links_seeded.jsonl", cdl_seeded)

    linked_doc_ids = sorted(
        {r.get("ContentDocumentId") for r in cdl_seeded if r.get("ContentDocumentId")}
    )
    missing_latest = [d for d in linked_doc_ids if d not in set(doc_ids)]
    report["counts"]["ContentDocumentId_missing_latest"] = len(missing_latest)
    _write_csv(
        links_dir / "probe_missing_latest_contentversion.csv",
        [{"ContentDocumentId": d} for d in missing_latest],
    )

    # 3) CombinedAttachment (skip quietly if not queryable in this org)
    _logger.info("Probe: CombinedAttachment (if accessible)…")
    ca_rows, err = _try_query_all(
        api,
        "SELECT Id, ParentId, Name, ContentType, BodyLength, CreatedDate, LastModifiedDate "
        "FROM CombinedAttachment",
    )
    if err and ("INVALID_TYPE_FOR_OPERATION" in err or "does not support query" in err):
        report["notes"].append("CombinedAttachment is not queryable in this org; skipped.")
        report["counts"]["CombinedAttachment"] = 0
    else:
        if err:
            report["errors"]["CombinedAttachment"] = err
        report["counts"]["CombinedAttachment"] = len(ca_rows)
        _write_jsonl(links_dir / "probe_combined_attachments.jsonl", ca_rows)

    # 4) EmailMessage (+ two attachment pathways)
    _logger.info("Probe: EmailMessage…")
    if email_bodies:
        email_soql = (
            "SELECT Id, ParentId, Subject, FromAddress, ToAddress, CcAddress, BccAddress, "
            "MessageDate, Incoming, Status, HasAttachment, TextBody, HtmlBody, "
            "CreatedDate, LastModifiedDate "
            "FROM EmailMessage"
        )
    else:
        email_soql = (
            "SELECT Id, ParentId, Subject, FromAddress, ToAddress, CcAddress, BccAddress, "
            "MessageDate, Incoming, Status, HasAttachment, CreatedDate, LastModifiedDate "
            "FROM EmailMessage"
        )

    em_rows, err = _try_query_all(api, email_soql)
    if err:
        report["errors"]["EmailMessage"] = err
    report["counts"]["EmailMessage"] = len(em_rows)
    _write_jsonl(links_dir / "probe_email_messages.jsonl", em_rows)

    email_ids_with_att = [
        r.get("Id") for r in em_rows if r.get("HasAttachment") is True and r.get("Id")
    ]
    report["counts"]["EmailMessage_HasAttachment_true"] = len(email_ids_with_att)

    # Attachment children of EmailMessage
    em_att_rows: List[Dict[str, Any]] = []
    if email_ids_with_att:
        _logger.info("Probe: Attachment WHERE ParentId IN (EmailMessage)…")
        for chunk in _chunk(email_ids_with_att, 500):
            in_list = ",".join(f"'{x}'" for x in chunk)
            rows, e = _try_query_all(
                api,
                "SELECT Id, ParentId, Name, ContentType, BodyLength, CreatedDate, LastModifiedDate "
                f"FROM Attachment WHERE ParentId IN ({in_list})",
            )
            if e:
                report.setdefault("errors", {}).setdefault(
                    "EmailMessage_AttachmentProbe", []
                ).append(e)
            em_att_rows.extend(rows)
    report["counts"]["EmailMessage_Attachments_via_Attachment"] = len(em_att_rows)
    _write_jsonl(links_dir / "probe_email_attachments_via_attachment.jsonl", em_att_rows)

    # Files linked to EmailMessage (this query is valid because it filters by LinkedEntityId IN)
    em_file_links: List[Dict[str, Any]] = []
    if email_ids_with_att:
        _logger.info("Probe: ContentDocumentLink WHERE LinkedEntityId IN (EmailMessage)…")
        for chunk in _chunk(email_ids_with_att, 500):
            in_list = ",".join(f"'{x}'" for x in chunk)
            rows, e = _try_query_all(
                api,
                "SELECT Id, ContentDocumentId, LinkedEntityId, ShareType, Visibility, SystemModstamp "
                f"FROM ContentDocumentLink WHERE LinkedEntityId IN ({in_list})",
            )
            if e:
                report.setdefault("errors", {}).setdefault("EmailMessage_FileLinkProbe", []).append(
                    e
                )
            em_file_links.extend(rows)
    report["counts"]["EmailMessage_Attachments_via_FilesLinks"] = len(em_file_links)
    _write_jsonl(links_dir / "probe_email_attachments_via_files_links.jsonl", em_file_links)

    # 5) Notes (classic + enhanced)
    _logger.info("Probe: Note (classic)…")
    note_rows, err = _try_query_all(
        api,
        "SELECT Id, ParentId, Title, Body, CreatedDate, LastModifiedDate FROM Note",
    )
    if err:
        report["errors"]["Note"] = err
    report["counts"]["Note"] = len(note_rows)
    _write_jsonl(links_dir / "probe_notes_classic.jsonl", note_rows)

    _logger.info("Probe: ContentNote (enhanced, if accessible)…")
    cn_rows, err = _try_query_all(
        api,
        "SELECT Id, Title, Content, CreatedDate, LastModifiedDate FROM ContentNote",
    )
    if err:
        report["errors"]["ContentNote"] = err
    report["counts"]["ContentNote"] = len(cn_rows)
    _write_jsonl(links_dir / "probe_notes_contentnote.jsonl", cn_rows)

    # 6) Chatter feed attachments
    _logger.info("Probe: FeedAttachment (if accessible)…")
    fa_rows, err = _try_query_all(
        api,
        "SELECT Id, FeedEntityId, RecordId, Type, Title FROM FeedAttachment",
    )
    if err:
        report["errors"]["FeedAttachment"] = err
    report["counts"]["FeedAttachment"] = len(fa_rows)
    _write_jsonl(links_dir / "probe_feed_attachments.jsonl", fa_rows)

    # --- write probe report
    _write_json(meta_dir / "probe_report.json", report)
    click.echo(f"✅ Probe report → {meta_dir / 'probe_report.json'}")

    # ------------------------------------------------------------
    # Optional: write manifest.json after probe
    # ------------------------------------------------------------
    if write_manifest:
        org_id = username = instance_url = api_version = ""
        try:
            who = api.whoami()
            org_id = who.get("organization_id", "") or ""
            username = who.get("preferred_username") or who.get("email") or ""
            instance_url = api.instance_url or ""
            api_version = api.api_version or ""
        except Exception:
            pass

        csv_root = str(Path(out_dir) / "csv")
        objects = scan_objects(csv_root)
        files = scan_files(out_dir)
        m = Manifest(
            generated_utc=_utc_now(),
            org_id=org_id,
            username=username,
            instance_url=instance_url,
            api_version=api_version,
            csv_root=csv_root,
            files=files,
            objects=objects,
        )
        path = str(Path(out_dir) / "manifest.json")
        write_manifest_file(path, m)
        click.echo(f"✅ Wrote manifest → {Path(path).resolve()}")
