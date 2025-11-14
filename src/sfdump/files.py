from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from tqdm import tqdm

from .utils import ensure_dir, sanitize_filename, sha256_of_file, write_csv


def _safe_target(files_root: str, suggested_name: str) -> str:
    safe = sanitize_filename(suggested_name) or "file"
    # shard into subdirs to avoid huge single directories
    sub = safe[:2].lower()
    return os.path.join(files_root, sub, safe)


def dump_content_versions(
    api,
    out_dir: str,
    *,
    where: Optional[str] = None,
    max_workers: int = 8,
) -> Dict[str, int | str | None]:
    """Download latest ContentVersion binaries + write metadata and links CSVs."""
    files_root = os.path.join(out_dir, "files")
    ensure_dir(files_root)

    # Only latest by default; allow extra filtering
    soql = (
        "SELECT Id, ContentDocumentId, Title, FileType, ContentSize, VersionNumber "
        "FROM ContentVersion WHERE IsLatest = true"
    )
    if where:
        soql += f" AND ({where})"

    rows = list(api.query_all_iter(soql))
    meta_rows: List[dict] = []
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for r in rows:
            r.pop("attributes", None)
            ext = f".{(r.get('FileType') or '').lower()}" if r.get("FileType") else ""
            fname = f"{r['ContentDocumentId']}_{sanitize_filename(r.get('Title') or 'file')}{ext}"
            target = _safe_target(files_root, fname)
            rel = f"/services/data/{api.api_version}/sobjects/ContentVersion/{r['Id']}/VersionData"
            futs[ex.submit(api.download_path_to_file, rel, target)] = (r, target)

        for fut in tqdm(as_completed(futs), total=len(futs), desc="Files (ContentVersion)"):
            r, target = futs[fut]
            try:
                size = fut.result()
                r["path"] = os.path.relpath(target, out_dir)
                r["sha256"] = sha256_of_file(target)
                total_bytes += size
            except Exception as e:  # keep going; record failure
                r["path"] = ""
                r["sha256"] = ""
                r["download_error"] = str(e)
            meta_rows.append(r)

    # Links (which record a file is attached to)
    doc_ids = {r.get("ContentDocumentId") for r in meta_rows if r.get("ContentDocumentId")}
    cdl_rows: List[dict] = []

    if doc_ids:
        ids_list = list(doc_ids)

        def _chunked(seq: List[str], size: int) -> List[List[str]]:
            return [seq[i : i + size] for i in range(0, len(seq), size)]

        for chunk in _chunked(ids_list, 200):
            in_list = ",".join(f"'{id_}'" for id_ in chunk)
            soql_links = (
                "SELECT ContentDocumentId, LinkedEntityId, ShareType, Visibility "
                "FROM ContentDocumentLink "
                f"WHERE ContentDocumentId IN ({in_list})"
            )
            part = list(api.query_all_iter(soql_links))
            for r in part:
                r.pop("attributes", None)
            cdl_rows.extend(part)

    links_dir = os.path.join(out_dir, "links")
    ensure_dir(links_dir)

    meta_csv = os.path.join(links_dir, "content_versions.csv")
    if meta_rows:
        fieldnames = sorted({k for r in meta_rows for k in r.keys()})
        write_csv(meta_csv, meta_rows, fieldnames)
    else:
        open(meta_csv, "w").close()

    cdl_csv = os.path.join(links_dir, "content_document_links.csv")
    if cdl_rows:
        write_csv(
            cdl_csv, cdl_rows, ["ContentDocumentId", "LinkedEntityId", "ShareType", "Visibility"]
        )
    else:
        open(cdl_csv, "w").close()

    return {
        "kind": "content_version",
        "meta_csv": meta_csv,
        "links_csv": cdl_csv,
        "count": len(meta_rows),
        "bytes": total_bytes,
        "root": files_root,
    }


def dump_attachments(
    api,
    out_dir: str,
    *,
    where: Optional[str] = None,
    max_workers: int = 8,
) -> Dict[str, int | str | None]:
    """Download legacy Attachment binaries + write metadata CSV."""
    files_root = os.path.join(out_dir, "files_legacy")
    ensure_dir(files_root)

    soql = "SELECT Id, ParentId, Name, BodyLength, ContentType FROM Attachment"
    if where:
        soql += f" WHERE {where}"

    rows = list(api.query_all_iter(soql))
    meta_rows: List[dict] = []
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for r in rows:
            r.pop("attributes", None)
            fname = f"{r['Id']}_{sanitize_filename(r.get('Name') or 'attachment')}"
            target = _safe_target(files_root, fname)
            rel = f"/services/data/{api.api_version}/sobjects/Attachment/{r['Id']}/Body"
            futs[ex.submit(api.download_path_to_file, rel, target)] = (r, target)

        for fut in tqdm(as_completed(futs), total=len(futs), desc="Files (Attachment)"):
            r, target = futs[fut]
            try:
                size = fut.result()
                r["path"] = os.path.relpath(target, out_dir)
                r["sha256"] = sha256_of_file(target)
                total_bytes += size
            except Exception as e:
                r["path"] = ""
                r["sha256"] = ""
                r["download_error"] = str(e)
            meta_rows.append(r)

    links_dir = os.path.join(out_dir, "links")
    ensure_dir(links_dir)
    meta_csv = os.path.join(links_dir, "attachments.csv")
    if meta_rows:
        fieldnames = sorted({k for r in meta_rows for k in r.keys()})
        write_csv(meta_csv, meta_rows, fieldnames)
    else:
        open(meta_csv, "w").close()

    return {
        "kind": "attachment",
        "meta_csv": meta_csv,
        "links_csv": None,
        "count": len(meta_rows),
        "bytes": total_bytes,
        "root": files_root,
    }
