from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class ObjectExport:
    name: str
    csv: str
    rows: int


@dataclass
class FilesExport:
    kind: str  # "content_version" | "attachment"
    meta_csv: str
    links_csv: Optional[str]
    count: int
    bytes: int
    root: str


@dataclass
class Manifest:
    generated_utc: str
    org_id: str
    username: str
    instance_url: str
    api_version: str
    csv_root: str
    files: List[FilesExport] = field(default_factory=list)
    objects: List[ObjectExport] = field(default_factory=list)


def _rel_if(path: Optional[str], base_dir: str) -> Optional[str]:
    if path is None:
        return None
    return os.path.relpath(os.path.abspath(path), os.path.abspath(base_dir))


def write_manifest(path: str, manifest: Manifest) -> str:
    """Write manifest.json with relative paths."""
    payload = asdict(manifest)
    base = os.path.dirname(os.path.abspath(path))

    payload["csv_root"] = _rel_if(payload["csv_root"], base)
    for f in payload["files"]:
        f["meta_csv"] = _rel_if(f["meta_csv"], base)
        f["links_csv"] = _rel_if(f.get("links_csv"), base) if f.get("links_csv") else None
        f["root"] = _rel_if(f["root"], base)
    for o in payload["objects"]:
        o["csv"] = _rel_if(o["csv"], base)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return path


# ---------- helpers to “scan” existing output (no API calls required) ----------


def _count_csv_rows(csv_path: str) -> int:
    """Count rows in a CSV (excluding header)."""
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            # subtract header if present
            return max(sum(1 for _ in reader) - 1, 0)
    except FileNotFoundError:
        return 0


def _sum_dir_bytes(root: str) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                pass
    return total


def scan_objects(csv_root: str) -> List[ObjectExport]:
    if not os.path.isdir(csv_root):
        return []
    out: List[ObjectExport] = []
    for fname in sorted(os.listdir(csv_root)):
        if not fname.lower().endswith(".csv"):
            continue
        name = os.path.splitext(fname)[0]
        path = os.path.join(csv_root, fname)
        out.append(ObjectExport(name=name, csv=path, rows=_count_csv_rows(path)))
    return out


def scan_files(out_dir: str) -> List[FilesExport]:
    links_dir = os.path.join(out_dir, "links")
    result: List[FilesExport] = []

    # ContentVersion
    meta_cv = os.path.join(links_dir, "content_versions.csv")
    links_cv = os.path.join(links_dir, "content_document_links.csv")
    root_cv = os.path.join(out_dir, "files")
    if os.path.exists(meta_cv):
        count = _count_csv_rows(meta_cv)
        bytes_ = _sum_dir_bytes(root_cv) if os.path.isdir(root_cv) else 0
        result.append(
            FilesExport(
                kind="content_version",
                meta_csv=meta_cv,
                links_csv=links_cv if os.path.exists(links_cv) else None,
                count=count,
                bytes=bytes_,
                root=root_cv,
            )
        )

    # Attachment
    meta_at = os.path.join(links_dir, "attachments.csv")
    root_at = os.path.join(out_dir, "files_legacy")
    if os.path.exists(meta_at):
        count = _count_csv_rows(meta_at)
        bytes_ = _sum_dir_bytes(root_at) if os.path.isdir(root_at) else 0
        result.append(
            FilesExport(
                kind="attachment",
                meta_csv=meta_at,
                links_csv=None,
                count=count,
                bytes=bytes_,
                root=root_at,
            )
        )
    return result
