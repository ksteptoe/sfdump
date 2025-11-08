from __future__ import annotations

import csv
import os
from typing import Any, Dict, Iterable, List


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


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
