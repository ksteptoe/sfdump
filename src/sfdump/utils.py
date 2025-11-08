from __future__ import annotations

import csv
import hashlib
import os
import re
from typing import Any, Dict, Iterable, List


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name: str, repl: str = "_") -> str:
    """
    Make a portable filename:
    - replace invalid characters (/:*?"<>| and whitespace) with `_`
    - strip leading/trailing separators
    - fallback to 'file' if empty
    """
    safe = re.sub(r'[\\/:*?"<>|\s]+', repl, name or "").strip(repl)
    return safe or "file"


def sha256_of_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    """
    Streaming SHA-256 of a file to avoid loading it fully into memory.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: str, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> int:
    """Write rows to CSV. Normalizes newlines in string values. Returns row count."""
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            fixed = {
                k: (v.replace("\r\n", "\n").replace("\r", "\n") if isinstance(v, str) else v)
                for k, v in row.items()
            }
            w.writerow(fixed)
            count += 1
    return count
