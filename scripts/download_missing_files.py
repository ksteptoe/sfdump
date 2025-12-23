from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _looks_like_url(s: str) -> bool:
    return s.startswith("https://") or s.startswith("http://")


def _request_json(url: str, access_token: str) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        data = resp.read().decode("utf-8")
    return json.loads(data)


def _request_bytes(url: str, access_token: str) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "*/*")
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return resp.read()


def _coerce_access_token(token_obj: Any) -> str:
    # Common sfdump setups return a bare token string
    if isinstance(token_obj, str):
        return token_obj.strip()

    if isinstance(token_obj, dict):
        tok = (
            token_obj.get("access_token") or token_obj.get("accessToken") or token_obj.get("token")
        )
        if tok:
            return str(tok).strip()

    tok = getattr(token_obj, "access_token", None) or getattr(token_obj, "accessToken", None)
    if tok:
        return str(tok).strip()

    raise SystemExit(
        f"Could not obtain access token from get_salesforce_token() return type={type(token_obj).__name__}"
    )


def _safe_filename(stem: str, ext: str) -> str:
    stem = (stem or "").strip()
    stem = re.sub(r"[^\w\-. ()]+", "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if not stem:
        stem = "file"
    if len(stem) > 120:
        stem = stem[:120].rstrip()
    ext = (ext or "").lstrip(".")
    return f"{stem}.{ext}" if ext else stem


def _get_latest_published_version_id(
    *,
    instance_url: str,
    access_token: str,
    api_version: str,
    content_document_id: str,
) -> str:
    url = f"{instance_url}/services/data/v{api_version}/sobjects/ContentDocument/{content_document_id}"
    data = _request_json(url, access_token)
    v = data.get("LatestPublishedVersionId") or data.get("LatestPublishedVersionId".lower())
    if not v:
        raise SystemExit(
            f"ContentDocument {content_document_id}: missing LatestPublishedVersionId (keys={sorted(data.keys())[:30]})"
        )
    return str(v)


def _download_content_version_versiondata(
    *,
    instance_url: str,
    access_token: str,
    api_version: str,
    content_version_id: str,
) -> bytes:
    url = (
        f"{instance_url}/services/data/v{api_version}/sobjects/"
        f"ContentVersion/{content_version_id}/VersionData"
    )
    return _request_bytes(url, access_token)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Download missing Salesforce Files referenced by master_documents_index.csv"
    )
    ap.add_argument("--export-root", required=True, help="Export root folder")
    ap.add_argument("--limit", type=int, default=200, help="Max downloads in this run")
    ap.add_argument(
        "--api-version", default="60.0", help="Salesforce REST API version (e.g. 60.0)."
    )
    ap.add_argument(
        "--access-token", default="", help="Override access token (or set SF_ACCESS_TOKEN)"
    )
    ap.add_argument(
        "--instance-url", default="", help="Override instance URL (or set SF_INSTANCE_URL)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Do not download; just report what would be done."
    )
    args = ap.parse_args()

    export_root = Path(args.export_root)
    index_path = export_root / "meta" / "master_documents_index.csv"
    files_root = export_root / "files"

    if not index_path.exists():
        raise SystemExit(f"Missing index: {index_path}")
    files_root.mkdir(parents=True, exist_ok=True)

    instance_url = (args.instance_url or os.environ.get("SF_INSTANCE_URL", "")).strip().rstrip("/")
    if not instance_url:
        raise SystemExit("Missing --instance-url (or SF_INSTANCE_URL).")

    access_token = (args.access_token or os.environ.get("SF_ACCESS_TOKEN", "")).strip()
    if not access_token:
        from sfdump.sf_auth import get_salesforce_token  # type: ignore

        access_token = _coerce_access_token(get_salesforce_token())

    # Read rows
    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "local_path" not in fieldnames:
        raise SystemExit("master_documents_index.csv has no 'local_path' column")

    # Missing "File" rows with a file_id that looks like ContentDocument(069) or ContentVersion(068)
    missing = [
        r
        for r in rows
        if (r.get("file_source") == "File")
        and (r.get("local_path") or "") == ""
        and (
            (r.get("file_id") or "").startswith("069") or (r.get("file_id") or "").startswith("068")
        )
    ]

    print(f"Index rows: {len(rows)}")
    print(
        f"Missing File rows (069=ContentDocument or 068=ContentVersion) with blank local_path: {len(missing)}"
    )
    if not missing:
        print("Nothing to do.")
        return 0

    todo = missing[: int(args.limit)]
    print(f"Will process: {len(todo)} (limit={args.limit}, dry_run={args.dry_run})")

    downloaded = 0
    failed = 0

    for r in todo:
        file_id = str(r.get("file_id") or "").strip()
        name = str(r.get("file_name") or "").strip()
        ext = str(r.get("file_extension") or "").strip()

        # Decide which id we need for VersionData
        try:
            if file_id.startswith("069"):
                # ContentDocument -> LatestPublishedVersionId (ContentVersion)
                ver_id = _get_latest_published_version_id(
                    instance_url=instance_url,
                    access_token=access_token,
                    api_version=str(args.api_version),
                    content_document_id=file_id,
                )
            elif file_id.startswith("068"):
                ver_id = file_id
            else:
                print(f"SKIP unsupported file_id: {file_id}")
                continue
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"FAIL resolve {file_id} HTTP {e.code}: {e.reason}")
            continue
        except Exception as e:
            failed += 1
            print(f"FAIL resolve {file_id}: {e}")
            continue

        subdir = files_root / file_id[:2]
        subdir.mkdir(parents=True, exist_ok=True)

        fname = _safe_filename(f"{file_id}_{name}", ext)
        rel_path = Path("files") / file_id[:2] / fname
        abs_path = export_root / rel_path

        if abs_path.exists():
            r["local_path"] = str(rel_path).replace("/", "\\")
            print(f"SKIP exists -> set local_path: {file_id} -> {r['local_path']}")
            continue

        if args.dry_run:
            print(f"DRY-RUN would download: {file_id} (via {ver_id}) -> {rel_path}")
            continue

        try:
            data = _download_content_version_versiondata(
                instance_url=instance_url,
                access_token=access_token,
                api_version=str(args.api_version),
                content_version_id=ver_id,
            )
            abs_path.write_bytes(data)
            r["local_path"] = str(rel_path).replace("/", "\\")
            downloaded += 1
            print(f"OK {file_id} (via {ver_id}) ({len(data)} bytes) -> {r['local_path']}")
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"FAIL download {file_id} (via {ver_id}) HTTP {e.code}: {e.reason}")
        except Exception as e:
            failed += 1
            print(f"FAIL download {file_id} (via {ver_id}): {e}")

    if not args.dry_run:
        tmp = index_path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(index_path)

    print(f"Downloaded: {downloaded}  Failed: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
