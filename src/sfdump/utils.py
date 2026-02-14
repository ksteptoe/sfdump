from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name: str, repl: str = "_") -> str:
    """
    Make a portable filename:

    - replace invalid characters ``/:*?"<>|`` and whitespace with ``_``
    - strip leading/trailing separators
    - fallback to ``file`` if empty
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


def find_file_on_disk(export_root: Path, file_id: str, file_source: str) -> str:
    """Try to locate a downloaded file on disk by its Salesforce ID.

    Uses the same naming convention as files.py: files are stored under
    ``<root>/<id[:2].lower()>/<id>_*`` where root is ``files/`` for
    ContentVersions (file_source="File") and ``files_legacy/`` for
    Attachments (file_source="Attachment").

    Returns the relative path (from export_root) if exactly one match is
    found, otherwise returns an empty string.
    """
    if not file_id:
        return ""

    if file_source.lower() == "attachment":
        root_name = "files_legacy"
    else:
        root_name = "files"

    shard = file_id[:2].lower()
    shard_dir = export_root / root_name / shard

    if not shard_dir.is_dir():
        return ""

    matches = list(shard_dir.glob(f"{file_id}_*"))
    if len(matches) == 1:
        return matches[0].relative_to(export_root).as_posix()

    return ""


def glob_to_regex(pattern: str) -> str:
    """Convert glob-style wildcards to regex.

    Supports:
      *      -> .*   (any characters)
      ?      -> .    (single character)
      [abc]  -> [abc] (character set)
      [1-5]  -> [1-5] (character range)
      [!abc] -> [^abc] (negated set, glob-style ! converted to ^)

    All other regex special characters are escaped for literal matching.
    """
    result = []
    i = 0
    n = len(pattern)

    while i < n:
        char = pattern[i]

        if char == "*":
            result.append(".*")
        elif char == "?":
            result.append(".")
        elif char == "[":
            # Character class - find matching ]
            j = i + 1
            # Handle negation: [! or [^
            if j < n and pattern[j] in "!^":
                j += 1
            # Handle ] as first char in class (literal])
            if j < n and pattern[j] == "]":
                j += 1
            # Find closing ]
            while j < n and pattern[j] != "]":
                j += 1
            if j < n:
                # Found complete character class
                class_content = pattern[i + 1 : j]
                # Convert glob negation ! to regex negation ^
                if class_content.startswith("!"):
                    class_content = "^" + class_content[1:]
                result.append("[" + class_content + "]")
                i = j
            else:
                # No closing ], escape the [
                result.append("\\[")
        elif char in r"\.{}()+^$|":
            result.append("\\" + char)
        else:
            result.append(char)

        i += 1

    return "".join(result)
