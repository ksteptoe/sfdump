"""
Export inventory system — single authoritative completeness check.

Inspects only local files (no Salesforce API calls) and produces a JSON
manifest with per-category status. Target runtime: <5 seconds.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status enum
# ---------------------------------------------------------------------------


class CategoryStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    WARNING = "WARNING"
    NOT_APPLICABLE = "N/A"
    NOT_CHECKED = "NOT_CHECKED"


# ---------------------------------------------------------------------------
# Category dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CsvCategory:
    status: CategoryStatus = CategoryStatus.NOT_CHECKED
    expected_objects: list[str] = field(default_factory=list)
    found_objects: list[str] = field(default_factory=list)
    missing_objects: list[str] = field(default_factory=list)
    extra_objects: list[str] = field(default_factory=list)
    expected_count: int = 0
    found_count: int = 0


@dataclass
class FileCategory:
    """Tracks Attachments or ContentVersions."""

    status: CategoryStatus = CategoryStatus.NOT_CHECKED
    expected: int = 0
    actual: int = 0
    missing: int = 0
    corrupt: int = 0
    verified: bool = False
    disk_bytes: int = 0


@dataclass
class InvoiceCategory:
    status: CategoryStatus = CategoryStatus.NOT_CHECKED
    expected: int = 0
    actual: int = 0
    missing: int = 0
    index_csv_exists: bool = False


@dataclass
class IndexCategory:
    status: CategoryStatus = CategoryStatus.NOT_CHECKED
    files_index_count: int = 0
    master_index_rows: int = 0
    master_rows_with_path: int = 0
    master_rows_missing_path: int = 0


@dataclass
class DatabaseCategory:
    status: CategoryStatus = CategoryStatus.NOT_CHECKED
    db_exists: bool = False
    table_count: int = 0
    table_names: list[str] = field(default_factory=list)
    total_rows: int = 0


@dataclass
class InventoryResult:
    csv_objects: CsvCategory = field(default_factory=CsvCategory)
    attachments: FileCategory = field(default_factory=FileCategory)
    content_versions: FileCategory = field(default_factory=FileCategory)
    invoices: InvoiceCategory = field(default_factory=InvoiceCategory)
    indexes: IndexCategory = field(default_factory=IndexCategory)
    database: DatabaseCategory = field(default_factory=DatabaseCategory)
    overall_status: CategoryStatus = CategoryStatus.NOT_CHECKED
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    export_root: str = ""

    def compute_overall(self) -> None:
        """Derive overall_status from category statuses."""
        statuses = [
            self.csv_objects.status,
            self.attachments.status,
            self.content_versions.status,
            self.invoices.status,
            self.indexes.status,
            self.database.status,
        ]
        if any(s == CategoryStatus.INCOMPLETE for s in statuses):
            self.overall_status = CategoryStatus.INCOMPLETE
        elif any(s == CategoryStatus.WARNING for s in statuses):
            self.overall_status = CategoryStatus.WARNING
        elif any(s == CategoryStatus.NOT_CHECKED for s in statuses):
            self.overall_status = CategoryStatus.WARNING
        else:
            # All are COMPLETE or N/A
            self.overall_status = CategoryStatus.COMPLETE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count_csv_rows(path: Path) -> int:
    """Count data rows in a CSV (excludes header). Returns 0 if file missing."""
    if not path.exists():
        return 0
    count = 0
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        for _ in reader:
            count += 1
    return count


def _count_files_fast(directory: Path) -> tuple[int, int]:
    """Count files and total bytes using os.scandir (fast). Returns (count, bytes)."""
    if not directory.exists():
        return 0, 0
    total_count = 0
    total_bytes = 0
    for entry in os.scandir(directory):
        if entry.is_file(follow_symlinks=False):
            total_count += 1
            try:
                total_bytes += entry.stat(follow_symlinks=False).st_size
            except OSError:
                pass
        elif entry.is_dir(follow_symlinks=False):
            sub_count, sub_bytes = _count_files_fast(Path(entry.path))
            total_count += sub_count
            total_bytes += sub_bytes
    return total_count, total_bytes


def _read_csv_column(path: Path, column: str) -> list[str]:
    """Read a single column from a CSV file."""
    if not path.exists():
        return []
    values = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            val = row.get(column, "").strip()
            if val:
                values.append(val)
    return values


# ---------------------------------------------------------------------------
# InventoryManager
# ---------------------------------------------------------------------------


class InventoryManager:
    def __init__(self, export_root: Path):
        self.root = Path(export_root).resolve()
        self.csv_dir = self.root / "csv"
        self.links_dir = self.root / "links"
        self.meta_dir = self.root / "meta"
        self.files_dir = self.root / "files"
        self.files_legacy_dir = self.root / "files_legacy"
        self.invoices_dir = self.root / "invoices"

    def run(self) -> InventoryResult:
        """Run all checks and return the inventory result."""
        t0 = time.monotonic()
        result = InventoryResult(export_root=str(self.root))

        result.csv_objects = self._check_csv_objects()
        result.attachments = self._check_attachments()
        result.content_versions = self._check_content_versions()
        result.invoices = self._check_invoices()
        result.indexes = self._check_indexes()
        result.database = self._check_database()

        result.duration_seconds = round(time.monotonic() - t0, 2)
        result.compute_overall()
        return result

    def write_manifest(self, result: InventoryResult) -> Path:
        """Write inventory result to meta/inventory.json."""
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.meta_dir / "inventory.json"

        data = _result_to_dict(result)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return out_path

    # ----- Individual checks --------------------------------------------------

    def _check_csv_objects(self) -> CsvCategory:
        """Check CSV exports against ESSENTIAL_OBJECTS list."""
        from .orchestrator import ESSENTIAL_OBJECTS

        cat = CsvCategory()

        if not self.csv_dir.exists():
            cat.status = CategoryStatus.NOT_CHECKED
            return cat

        cat.expected_objects = list(ESSENTIAL_OBJECTS)
        cat.expected_count = len(ESSENTIAL_OBJECTS)

        # Find actual CSVs on disk
        actual_csvs = {f.stem for f in self.csv_dir.glob("*.csv") if f.is_file()}
        cat.found_objects = sorted(actual_csvs)
        cat.found_count = len(actual_csvs)

        expected_set = set(ESSENTIAL_OBJECTS)
        cat.missing_objects = sorted(expected_set - actual_csvs)
        cat.extra_objects = sorted(actual_csvs - expected_set)

        # Status: COMPLETE if all expected CSVs exist (extras are fine)
        if not cat.missing_objects:
            cat.status = CategoryStatus.COMPLETE
        else:
            cat.status = CategoryStatus.INCOMPLETE

        return cat

    def _check_attachments(self) -> FileCategory:
        """Check legacy Attachment file downloads."""
        cat = FileCategory()
        meta_csv = self.links_dir / "attachments.csv"

        if not meta_csv.exists():
            cat.status = CategoryStatus.NOT_CHECKED
            return cat

        cat.expected = _count_csv_rows(meta_csv)
        cat.actual, cat.disk_bytes = _count_files_fast(self.files_legacy_dir)

        # Check verify output for detailed counts
        missing_csv = self.links_dir / "attachments_missing.csv"
        corrupt_csv = self.links_dir / "attachments_corrupt.csv"

        if missing_csv.exists():
            cat.missing = _count_csv_rows(missing_csv)
            cat.verified = True

        if corrupt_csv.exists():
            cat.corrupt = _count_csv_rows(corrupt_csv)
            cat.verified = True

        # If verify outputs don't exist, infer from counts
        if not cat.verified:
            cat.missing = max(0, cat.expected - cat.actual)

        if cat.missing == 0 and cat.corrupt == 0:
            cat.status = CategoryStatus.COMPLETE
        elif cat.corrupt > 0:
            cat.status = CategoryStatus.WARNING
        else:
            cat.status = CategoryStatus.INCOMPLETE

        return cat

    def _check_content_versions(self) -> FileCategory:
        """Check ContentVersion file downloads."""
        cat = FileCategory()
        meta_csv = self.links_dir / "content_versions.csv"

        if not meta_csv.exists():
            cat.status = CategoryStatus.NOT_CHECKED
            return cat

        cat.expected = _count_csv_rows(meta_csv)
        cat.actual, cat.disk_bytes = _count_files_fast(self.files_dir)

        # Check verify output
        missing_csv = self.links_dir / "content_versions_missing.csv"
        corrupt_csv = self.links_dir / "content_versions_corrupt.csv"

        if missing_csv.exists():
            cat.missing = _count_csv_rows(missing_csv)
            cat.verified = True

        if corrupt_csv.exists():
            cat.corrupt = _count_csv_rows(corrupt_csv)
            cat.verified = True

        if not cat.verified:
            cat.missing = max(0, cat.expected - cat.actual)

        if cat.missing == 0 and cat.corrupt == 0:
            cat.status = CategoryStatus.COMPLETE
        elif cat.corrupt > 0:
            cat.status = CategoryStatus.WARNING
        else:
            cat.status = CategoryStatus.INCOMPLETE

        return cat

    def _check_invoices(self) -> InvoiceCategory:
        """Check invoice PDF downloads."""
        cat = InvoiceCategory()
        invoice_csv = self.csv_dir / "c2g__codaInvoice__c.csv"

        if not invoice_csv.exists():
            cat.status = CategoryStatus.NOT_APPLICABLE
            return cat

        # Count Complete invoices
        try:
            from .command_sins import read_invoices

            invoices = read_invoices(invoice_csv, status_filter="Complete")
            cat.expected = len(invoices)
        except Exception:
            _logger.debug("Could not read invoice CSV", exc_info=True)
            cat.status = CategoryStatus.NOT_CHECKED
            return cat

        if cat.expected == 0:
            cat.status = CategoryStatus.NOT_APPLICABLE
            return cat

        # Count actual PDFs
        if self.invoices_dir.exists():
            cat.actual = sum(
                1
                for f in self.invoices_dir.iterdir()
                if f.is_file() and f.suffix == ".pdf" and f.stat().st_size > 0
            )
        cat.missing = cat.expected - cat.actual

        # Check for index CSV
        idx = self.links_dir / "c2g__codaInvoice__c_invoice_pdfs_files_index.csv"
        cat.index_csv_exists = idx.exists()

        if cat.missing <= 0:
            cat.status = CategoryStatus.COMPLETE
            cat.missing = 0
        else:
            cat.status = CategoryStatus.INCOMPLETE

        return cat

    def _check_indexes(self) -> IndexCategory:
        """Check document index files."""
        cat = IndexCategory()

        if not self.links_dir.exists():
            cat.status = CategoryStatus.NOT_CHECKED
            return cat

        # Count *_files_index.csv files
        index_files = list(self.links_dir.glob("*_files_index.csv"))
        cat.files_index_count = len(index_files)

        # Check master index
        master_path = self.meta_dir / "master_documents_index.csv"
        if master_path.exists():
            with master_path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cat.master_index_rows += 1
                    local_path = (row.get("local_path") or "").strip()
                    if local_path:
                        cat.master_rows_with_path += 1
                    else:
                        cat.master_rows_missing_path += 1

        if cat.files_index_count == 0 and cat.master_index_rows == 0:
            cat.status = CategoryStatus.NOT_CHECKED
        elif cat.master_rows_missing_path > 0:
            cat.status = CategoryStatus.WARNING
        else:
            cat.status = CategoryStatus.COMPLETE

        return cat

    def _check_database(self) -> DatabaseCategory:
        """Check SQLite database."""
        cat = DatabaseCategory()
        db_path = self.meta_dir / "sfdata.db"

        if not db_path.exists():
            cat.status = CategoryStatus.INCOMPLETE
            return cat

        cat.db_exists = True

        try:
            from .viewer.db_inspect import inspect_sqlite_db

            overview = inspect_sqlite_db(db_path)
            cat.table_count = len(overview.tables)
            cat.table_names = [t.name for t in overview.tables]
            cat.total_rows = sum(t.row_count for t in overview.tables)
            cat.status = CategoryStatus.COMPLETE
        except Exception:
            _logger.debug("Could not inspect database", exc_info=True)
            cat.status = CategoryStatus.WARNING

        return cat


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _result_to_dict(result: InventoryResult) -> dict[str, Any]:
    """Convert InventoryResult to a JSON-friendly dict."""
    data = asdict(result)
    # Enum values → strings
    _stringify_enums(data)
    return data


def _stringify_enums(obj: Any) -> None:
    """Recursively convert Enum values to their .value string."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Enum):
                obj[k] = v.value
            elif isinstance(v, (dict, list)):
                _stringify_enums(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, Enum):
                obj[i] = v.value
            elif isinstance(v, (dict, list)):
                _stringify_enums(v)
