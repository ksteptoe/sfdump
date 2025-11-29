from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from tqdm import tqdm

from .utils import ensure_dir, sanitize_filename, sha256_of_file, write_csv

_logger = logging.getLogger(__name__)


def _order_and_chunk_rows(rows: List[dict], *, kind: str) -> List[dict]:
    """Optionally reorder and slice rows based on env vars.

    Env vars:
      SFDUMP_FILES_ORDER         = 'asc' | 'desc' (by Id, default = no reordering)
      SFDUMP_FILES_CHUNK_TOTAL   = integer > 0 (number of chunks)
      SFDUMP_FILES_CHUNK_INDEX   = 1-based index of the chunk to process

    When no env vars are set, rows are returned unchanged.
    """
    order = os.getenv("SFDUMP_FILES_ORDER", "").strip().lower()
    if order in {"asc", "desc"}:
        reverse = order == "desc"
        try:
            rows = sorted(rows, key=lambda r: r.get("Id"), reverse=reverse)
            _logger.info(
                "Applying %s ordering to %s rows for %s",
                order,
                len(rows),
                kind,
            )
        except Exception as e:  # pragma: no cover
            _logger.warning("Failed to apply %s ordering for %s: %s", order, kind, e)

    chunk_total_raw = os.getenv("SFDUMP_FILES_CHUNK_TOTAL", "").strip()
    chunk_index_raw = os.getenv("SFDUMP_FILES_CHUNK_INDEX", "").strip()

    if not chunk_total_raw:
        return rows  # no chunking requested

    try:
        chunk_total = int(chunk_total_raw)
        chunk_index = int(chunk_index_raw or "1")
    except ValueError:
        _logger.warning(
            "Invalid chunk env values: SFDUMP_FILES_CHUNK_TOTAL=%r "
            "SFDUMP_FILES_CHUNK_INDEX=%r; ignoring chunking",
            chunk_total_raw,
            chunk_index_raw,
        )
        return rows

    if chunk_total <= 0:
        return rows

    if not (1 <= chunk_index <= chunk_total):
        _logger.warning(
            "Chunk index %d out of range 1..%d for %s; ignoring chunking",
            chunk_index,
            chunk_total,
            kind,
        )
        return rows

    n = len(rows)
    if n == 0:
        return rows

    # ceil division
    chunk_size = (n + chunk_total - 1) // chunk_total
    start = (chunk_index - 1) * chunk_size
    end = min(start + chunk_size, n)

    if start >= n:
        _logger.warning(
            "Chunk %d/%d for %s is empty (start=%d >= total_rows=%d); " "no rows will be processed",
            chunk_index,
            chunk_total,
            kind,
            start,
            n,
        )
        return []

    _logger.info(
        "Applying chunking for %s: chunk %d/%d, total_rows=%d, " "chunk_size=%d, start=%d, end=%d",
        kind,
        chunk_index,
        chunk_total,
        n,
        chunk_size,
        start,
        end,
    )
    return rows[start:end]


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
    """Download latest ContentVersion binaries + write metadata and links CSVs.

    Now resume-aware:
    - If a target file already exists and is non-zero length, we skip the API call
      and just record its path + sha256.
    """
    files_root = os.path.join(out_dir, "files")
    ensure_dir(files_root)

    soql = (
        "SELECT Id, ContentDocumentId, Title, FileType, ContentSize, VersionNumber "
        "FROM ContentVersion"
    )
    if where:
        soql += f" WHERE ({where})"

    _logger.info("dump_content_versions SOQL: %s", soql)

    rows = list(api.query_all_iter(soql))
    rows = _order_and_chunk_rows(rows, kind="content_version")
    meta_rows: List[dict] = []
    total_bytes = 0

    discovered_initial = len(rows)
    _logger.info(
        "dump_content_versions: discovered %d ContentVersion rows (where=%r)",
        discovered_initial,
        where,
    )

    skipped_existing = 0
    downloaded_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for r in rows:
            r.pop("attributes", None)
            ext = f".{(r.get('FileType') or '').lower()}" if r.get("FileType") else ""
            fname = f"{r['ContentDocumentId']}_{sanitize_filename(r.get('Title') or 'file')}{ext}"
            target = _safe_target(files_root, fname)

            # Resume-awareness: skip files that already exist and are non-empty
            if os.path.exists(target) and os.path.getsize(target) > 0:
                r["path"] = os.path.relpath(target, out_dir)
                r["sha256"] = sha256_of_file(target)
                skipped_existing += 1
                meta_rows.append(r)
                _logger.debug(
                    "dump_content_versions: skipping existing file for ContentDocumentId=%s at %s",
                    r.get("ContentDocumentId") or r.get("Id"),
                    target,
                )
                continue

            rel = (
                f"/services/data/{api.api_version}/sobjects/"
                f"ContentVersion/{r['Id']}/VersionData"
            )
            futs[ex.submit(api.download_path_to_file, rel, target)] = (r, target)

        # Only iterate futures for files that actually need downloading
        if futs:
            for fut in tqdm(
                as_completed(futs),
                total=len(futs),
                desc="Files (ContentVersion)",
            ):
                r, target = futs[fut]
                try:
                    size = fut.result()
                    r["path"] = os.path.relpath(target, out_dir)
                    r["sha256"] = sha256_of_file(target)
                    total_bytes += size
                    downloaded_count += 1
                except Exception as e:  # keep going; record failure
                    r["path"] = ""
                    r["sha256"] = ""
                    r["download_error"] = str(e)
                    error_count += 1
                    _logger.warning(
                        "dump_content_versions: failed to download File %s (%s): %s",
                        r.get("Id") or r.get("ContentDocumentId"),
                        r.get("Title") or r.get("file_name") or r.get("Name"),
                        e,
                    )
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
            cdl_csv,
            cdl_rows,
            ["ContentDocumentId", "LinkedEntityId", "ShareType", "Visibility"],
        )
    else:
        open(cdl_csv, "w").close()

    discovered_count = len(meta_rows)
    # Futures represent files where an API call was attempted this run
    attempted_downloads = len(futs)
    if discovered_count != discovered_initial:
        _logger.warning(
            "dump_content_versions: meta_rows count (%d) differs from discovered_initial (%d)",
            discovered_count,
            discovered_initial,
        )

    _logger.info(
        (
            "dump_content_versions: discovered=%d, attempted_downloads=%d, "
            "skipped_existing=%d, downloaded=%d, errors=%d, bytes=%d, meta_csv=%s"
        ),
        discovered_count,
        attempted_downloads,
        skipped_existing,
        downloaded_count,
        error_count,
        total_bytes,
        meta_csv,
    )

    return {
        "kind": "content_version",
        "meta_csv": meta_csv,
        "links_csv": cdl_csv,
        "count": discovered_count,
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
    """Download legacy Attachment binaries + write metadata CSV.

    Now resume-aware:
    - If a target file already exists and is non-zero length, we skip the API call
      and just record its path + sha256.
    """
    files_root = os.path.join(out_dir, "files_legacy")
    ensure_dir(files_root)

    soql = "SELECT Id, ParentId, Name, BodyLength, ContentType FROM Attachment"
    if where:
        soql += f" WHERE {where}"

    rows = list(api.query_all_iter(soql))
    rows = _order_and_chunk_rows(rows, kind="attachment")
    meta_rows: List[dict] = []
    total_bytes = 0

    discovered_initial = len(rows)
    _logger.info(
        "dump_attachments: discovered %d Attachment rows (where=%r)",
        discovered_initial,
        where,
    )

    skipped_existing = 0
    downloaded_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {}
        for r in rows:
            r.pop("attributes", None)
            fname = f"{r['Id']}_{sanitize_filename(r.get('Name') or 'attachment')}"
            target = _safe_target(files_root, fname)

            # Resume-awareness: skip files that already exist and are non-empty
            if os.path.exists(target) and os.path.getsize(target) > 0:
                r["path"] = os.path.relpath(target, out_dir)
                r["sha256"] = sha256_of_file(target)
                skipped_existing += 1
                meta_rows.append(r)
                _logger.debug(
                    "dump_attachments: skipping existing Attachment %s at %s",
                    r.get("Id"),
                    target,
                )
                continue

            rel = f"/services/data/{api.api_version}/sobjects/Attachment/{r['Id']}/Body"
            futs[ex.submit(api.download_path_to_file, rel, target)] = (r, target)

        # Only iterate futures for files that actually need downloading
        if futs:
            for fut in tqdm(
                as_completed(futs),
                total=len(futs),
                desc="Files (Attachment)",
            ):
                r, target = futs[fut]
                try:
                    size = fut.result()
                    r["path"] = os.path.relpath(target, out_dir)
                    r["sha256"] = sha256_of_file(target)
                    total_bytes += size
                    downloaded_count += 1
                except Exception as e:
                    r["path"] = ""
                    r["sha256"] = ""
                    r["download_error"] = str(e)
                    error_count += 1
                    _logger.warning(
                        "dump_attachments: failed to download Attachment %s (%s): %s",
                        r.get("Id"),
                        r.get("Name"),
                        e,
                    )
                meta_rows.append(r)

    links_dir = os.path.join(out_dir, "links")
    ensure_dir(links_dir)
    meta_csv = os.path.join(links_dir, "attachments.csv")
    if meta_rows:
        fieldnames = sorted({k for r in meta_rows for k in r.keys()})
        write_csv(meta_csv, meta_rows, fieldnames)
    else:
        open(meta_csv, "w").close()

    discovered_count = len(meta_rows)
    attempted_downloads = len(futs)
    if discovered_count != discovered_initial:
        _logger.warning(
            "dump_attachments: meta_rows count (%d) differs from discovered_initial (%d)",
            discovered_count,
            discovered_initial,
        )

    _logger.info(
        (
            "dump_attachments: discovered=%d, attempted_downloads=%d, "
            "skipped_existing=%d, downloaded=%d, errors=%d, bytes=%d, meta_csv=%s"
        ),
        discovered_count,
        attempted_downloads,
        skipped_existing,
        downloaded_count,
        error_count,
        total_bytes,
        meta_csv,
    )

    return {
        "kind": "attachment",
        "meta_csv": meta_csv,
        "links_csv": None,
        "count": discovered_count,
        "bytes": total_bytes,
        "root": files_root,
    }


def estimate_content_versions(
    api,
    *,
    where: Optional[str] = None,
) -> Dict[str, int | str | None]:
    """Estimate total size of latest ContentVersion files (no download)."""
    soql = (
        "SELECT Id, ContentDocumentId, Title, FileType, ContentSize, VersionNumber "
        "FROM ContentVersion WHERE IsLatest = true"
    )
    if where:
        soql += f" AND ({where})"

    count = 0
    total_bytes = 0

    for r in api.query_all_iter(soql):
        # ContentSize is an int (bytes) but be defensive:
        size = r.get("ContentSize") or 0
        count += 1
        total_bytes += int(size)

    return {
        "kind": "content_version (estimate)",
        "meta_csv": None,
        "links_csv": None,
        "count": count,
        "bytes": total_bytes,
        "root": "(estimate only)",
    }


def estimate_attachments(
    api,
    *,
    where: Optional[str] = None,
) -> Dict[str, int | str | None]:
    """Estimate total size of legacy Attachments (no download)."""
    soql = "SELECT Id, ParentId, Name, BodyLength, ContentType FROM Attachment"
    if where:
        soql += f" WHERE {where}"

    count = 0
    total_bytes = 0

    for r in api.query_all_iter(soql):
        size = r.get("BodyLength") or 0
        count += 1
        total_bytes += int(size)

    return {
        "kind": "attachment (estimate)",
        "meta_csv": None,
        "links_csv": None,
        "count": count,
        "bytes": total_bytes,
        "root": "(estimate only)",
    }
