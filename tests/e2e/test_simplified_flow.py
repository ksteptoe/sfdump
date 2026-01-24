"""
End-to-end test for the simplified SF export flow.

This test is NOT run in CI by default. To run manually:

    SF_E2E_TESTS=true pytest tests/e2e/ -v

For CI (lightweight mode - fewer objects, limited files):

    SF_E2E_TESTS=true SF_E2E_LIGHT=true pytest tests/e2e/ -v

Requirements:
    - Valid Salesforce credentials in .env file or environment
    - Network access to Salesforce
    - Sufficient disk space for exports (~2GB light, ~50GB full)
"""

from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

import pytest

# Skip entire module unless SF_E2E_TESTS is set
pytestmark = pytest.mark.skipif(
    os.environ.get("SF_E2E_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="E2E tests disabled. Set SF_E2E_TESTS=true to run.",
)

# Check if running in light mode (for CI)
IS_LIGHT_MODE = os.environ.get("SF_E2E_LIGHT", "").lower() in ("1", "true", "yes")


class TestSimplifiedExportFlow:
    """End-to-end test of the sf dump simplified export flow."""

    @pytest.fixture(autouse=True)
    def setup_export_dir(self, tmp_path: Path):
        """Create a temporary export directory."""
        self.export_path = tmp_path / "exports" / "export-test"
        self.export_path.mkdir(parents=True)
        yield
        # Cleanup is handled by pytest tmp_path

    def test_full_export_pipeline(self):
        """
        Test the complete export pipeline:
        1. Authentication
        2. File export (Attachments + ContentVersions)
        3. CSV export
        4. Index building
        5. Database building
        6. Verify all artifacts

        In light mode (SF_E2E_LIGHT=true), uses fewer objects and limits files
        for faster CI runs (~2GB instead of ~50GB).
        """
        from sfdump.orchestrator import run_full_export

        # Run the export (light mode for CI, full mode for manual testing)
        result = run_full_export(
            export_path=self.export_path,
            retry=False,
            verbose=True,
            light=IS_LIGHT_MODE,
            max_files=50 if IS_LIGHT_MODE else None,
        )

        if IS_LIGHT_MODE:
            print("\n[Running in LIGHT mode - limited objects and files]")

        # Basic assertions on result
        assert result.success, f"Export failed: {result.error}"
        assert result.export_path == self.export_path
        assert result.objects_exported > 0, "No objects were exported"

        # Run detailed verification
        self._verify_directory_structure()
        self._verify_csv_files()
        self._verify_database(result.database_path)
        self._verify_file_metadata()
        self._verify_files_accessible()

    def _verify_directory_structure(self):
        """Verify expected directories exist."""
        expected_dirs = ["csv", "links", "meta"]
        for dir_name in expected_dirs:
            dir_path = self.export_path / dir_name
            assert dir_path.exists(), f"Missing directory: {dir_name}"
            assert dir_path.is_dir(), f"Not a directory: {dir_name}"

        # At least one of files or files_legacy should exist if files were exported
        files_dir = self.export_path / "files"
        files_legacy_dir = self.export_path / "files_legacy"
        has_files = files_dir.exists() or files_legacy_dir.exists()
        # Note: files might be empty if SF org has no attachments
        print(f"Files directory exists: {has_files}")

    def _verify_csv_files(self):
        """Verify CSV files exist and have valid structure."""
        csv_dir = self.export_path / "csv"
        csv_files = list(csv_dir.glob("*.csv"))

        assert len(csv_files) > 0, "No CSV files found in export"
        print(f"Found {len(csv_files)} CSV files")

        # Verify each CSV has valid structure
        for csv_file in csv_files:
            self._verify_csv_structure(csv_file)

    def _verify_csv_structure(self, csv_path: Path):
        """Verify a CSV file has valid structure with headers and data."""
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

            assert headers is not None, f"CSV {csv_path.name} has no headers"
            assert len(headers) > 0, f"CSV {csv_path.name} has empty headers"
            assert "Id" in headers, f"CSV {csv_path.name} missing Id column"

            # Count rows (at least verify it's readable)
            row_count = sum(1 for _ in reader)
            print(f"  {csv_path.name}: {row_count} rows, {len(headers)} columns")

    def _verify_database(self, db_path: Path | None):
        """Verify SQLite database exists and has valid structure."""
        assert db_path is not None, "Database path is None"
        assert db_path.exists(), f"Database not found: {db_path}"
        assert db_path.stat().st_size > 0, "Database is empty"

        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()

            # Get all tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            assert len(tables) > 0, "Database has no tables"
            print(f"Database has {len(tables)} tables: {', '.join(tables[:10])}...")

            # Verify each table has data and valid structure
            for table in tables:
                self._verify_table(cur, table)

        finally:
            conn.close()

    def _verify_table(self, cur: sqlite3.Cursor, table: str):
        """Verify a database table has valid structure and data."""
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM [{table}]")
        count = cur.fetchone()[0]
        print(f"  Table {table}: {count} rows")

        # Get column info
        cur.execute(f"PRAGMA table_info([{table}])")
        columns = cur.fetchall()
        column_names = [col[1] for col in columns]

        assert len(column_names) > 0, f"Table {table} has no columns"

        # Internal/index tables that don't follow Salesforce Id convention
        internal_tables = {"record_documents", "sqlite_sequence"}

        # Verify Id column exists (Salesforce standard) - skip internal tables
        if table.lower() not in internal_tables:
            id_columns = [c for c in column_names if c.lower() == "id"]
            assert len(id_columns) > 0, f"Table {table} missing Id column"

    def _verify_file_metadata(self):
        """Verify file metadata CSVs in links directory."""
        links_dir = self.export_path / "links"

        # Check for attachments metadata
        attachments_csv = links_dir / "attachments.csv"
        if attachments_csv.exists():
            self._verify_file_metadata_csv(attachments_csv, "attachment")

        # Check for content versions metadata
        cv_csv = links_dir / "content_versions.csv"
        if cv_csv.exists():
            self._verify_file_metadata_csv(cv_csv, "content_version")

    def _verify_file_metadata_csv(self, csv_path: Path, file_type: str):
        """Verify a file metadata CSV has expected structure."""
        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            print(f"  {file_type} metadata: empty (no files)")
            return

        print(f"  {file_type} metadata: {len(rows)} entries")

        # Check expected columns
        sample = rows[0]
        assert "Id" in sample, f"{file_type} metadata missing Id"
        assert "path" in sample, f"{file_type} metadata missing path"

        # Count files with paths vs errors
        with_path = sum(1 for r in rows if r.get("path"))
        with_error = sum(1 for r in rows if r.get("download_error"))
        print(f"    With path: {with_path}, With error: {with_error}")

    def _verify_files_accessible(self):
        """Verify that file paths in metadata point to actual files."""
        links_dir = self.export_path / "links"

        total_checked = 0
        total_found = 0
        total_missing = 0

        # Check attachments
        attachments_csv = links_dir / "attachments.csv"
        if attachments_csv.exists():
            checked, found, missing = self._verify_file_paths(
                attachments_csv, "attachments"
            )
            total_checked += checked
            total_found += found
            total_missing += missing

        # Check content versions
        cv_csv = links_dir / "content_versions.csv"
        if cv_csv.exists():
            checked, found, missing = self._verify_file_paths(
                cv_csv, "content_versions"
            )
            total_checked += checked
            total_found += found
            total_missing += missing

        print("\nFile accessibility summary:")
        print(f"  Total checked: {total_checked}")
        print(f"  Found: {total_found}")
        print(f"  Missing: {total_missing}")

        if total_checked > 0:
            success_rate = (total_found / total_checked) * 100
            print(f"  Success rate: {success_rate:.1f}%")
            # Allow some tolerance for very large exports
            assert success_rate >= 95.0, f"Too many missing files: {success_rate:.1f}%"

    def _verify_file_paths(
        self, csv_path: Path, file_type: str
    ) -> tuple[int, int, int]:
        """
        Verify file paths in a metadata CSV point to actual files.

        Returns:
            Tuple of (checked, found, missing) counts
        """
        checked = 0
        found = 0
        missing = 0
        missing_examples = []

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                path = row.get("path", "").strip()
                if not path:
                    continue  # Skip entries without path (errors)

                checked += 1
                full_path = self.export_path / path

                if full_path.exists():
                    found += 1
                    # Verify file is not empty
                    if full_path.stat().st_size == 0:
                        print(f"  Warning: Empty file: {path}")
                else:
                    missing += 1
                    if len(missing_examples) < 5:
                        missing_examples.append(path)

        print(f"\n  {file_type}: checked={checked}, found={found}, missing={missing}")
        if missing_examples:
            print(f"    Missing examples: {missing_examples[:3]}")

        return checked, found, missing


class TestSimplifiedCLI:
    """Test the simplified CLI commands."""

    @pytest.fixture(autouse=True)
    def setup_workdir(self, tmp_path: Path, monkeypatch):
        """Set up a temporary working directory."""
        self.workdir = tmp_path
        monkeypatch.chdir(tmp_path)
        yield

    def test_sf_status_no_exports(self):
        """Test sf status when no exports exist."""
        from click.testing import CliRunner

        from sfdump.cli_simple import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "No exports found" in result.output

    def test_sf_test_connection(self):
        """Test sf test command verifies connection."""
        from click.testing import CliRunner

        from sfdump.cli_simple import cli

        # Create a minimal .env file
        env_file = self.workdir / ".env"
        env_file.write_text(
            """
SF_CLIENT_ID=test
SF_CLIENT_SECRET=test
SF_USERNAME=test@example.com
SF_PASSWORD=testpass
"""
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["test"])

        # Should attempt connection (may fail with invalid creds, but should run)
        assert result.exit_code in (0, 1)
        assert "Testing Salesforce Connection" in result.output

    @pytest.mark.skipif(IS_LIGHT_MODE, reason="CLI dump test skipped in light mode (use test_full_export_pipeline instead)")
    def test_sf_dump_full_export(self):
        """Test sf dump command runs full export.

        Skipped in light mode - CLI doesn't support light mode flag.
        The test_full_export_pipeline test covers export functionality with light mode.
        """
        from click.testing import CliRunner

        from sfdump.cli_simple import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["dump", "-v"])

        # Should complete (success or fail based on creds)
        assert "SF Data Export" in result.output

        if result.exit_code == 0:
            # Verify export directory created
            exports_dir = self.workdir / "exports"
            assert exports_dir.exists(), "Exports directory not created"

            # Find the export directory
            export_dirs = list(exports_dir.glob("export-*"))
            assert len(export_dirs) > 0, "No export directory created"

            export_path = export_dirs[0]

            # Verify basic structure
            assert (export_path / "csv").exists(), "CSV directory missing"
            assert (export_path / "meta").exists(), "Meta directory missing"
            assert (export_path / "links").exists(), "Links directory missing"


class TestDatabaseIntegrity:
    """Detailed database integrity tests."""

    @pytest.fixture
    def populated_db(self, tmp_path: Path) -> Path:
        """Run an export and return the database path."""
        from sfdump.orchestrator import run_full_export

        export_path = tmp_path / "exports" / "export-test"
        export_path.mkdir(parents=True)

        result = run_full_export(
            export_path=export_path,
            retry=False,
            verbose=False,
            light=IS_LIGHT_MODE,
            max_files=50 if IS_LIGHT_MODE else None,
        )

        if not result.success:
            pytest.skip(f"Export failed: {result.error}")

        if result.database_path is None or not result.database_path.exists():
            pytest.skip("Database not created")

        self.export_path = export_path
        return result.database_path

    def test_database_foreign_key_relationships(self, populated_db: Path):
        """Test that foreign key relationships are valid."""
        conn = sqlite3.connect(str(populated_db))
        try:
            cur = conn.cursor()

            # Get all tables
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            # Check for common relationship patterns
            relationships_to_check = [
                ("contact", "accountid", "account", "id"),
                ("opportunity", "accountid", "account", "id"),
                ("opportunitylineitem", "opportunityid", "opportunity", "id"),
            ]

            for child_table, fk_col, parent_table, pk_col in relationships_to_check:
                child_lower = child_table.lower()
                parent_lower = parent_table.lower()

                # Find matching tables (case-insensitive)
                child_match = next(
                    (t for t in tables if t.lower() == child_lower), None
                )
                parent_match = next(
                    (t for t in tables if t.lower() == parent_lower), None
                )

                if child_match and parent_match:
                    self._verify_relationship(
                        cur, child_match, fk_col, parent_match, pk_col
                    )

        finally:
            conn.close()

    def _verify_relationship(
        self,
        cur: sqlite3.Cursor,
        child_table: str,
        fk_col: str,
        parent_table: str,
        pk_col: str,
    ):
        """Verify a foreign key relationship has valid references."""
        # Get column names for child table
        cur.execute(f"PRAGMA table_info([{child_table}])")
        child_columns = [col[1].lower() for col in cur.fetchall()]

        if fk_col.lower() not in child_columns:
            print(f"  Skipping {child_table}.{fk_col} -> {parent_table}: column not found")
            return

        # Find the actual column name (case may differ)
        actual_fk_col = next(
            c for c in child_columns if c.lower() == fk_col.lower()
        )

        # Count orphaned records
        query = f"""
            SELECT COUNT(*) FROM [{child_table}] c
            WHERE c.[{actual_fk_col}] IS NOT NULL
            AND c.[{actual_fk_col}] != ''
            AND NOT EXISTS (
                SELECT 1 FROM [{parent_table}] p
                WHERE p.[{pk_col}] = c.[{actual_fk_col}]
            )
        """

        try:
            cur.execute(query)
            orphan_count = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM [{child_table}]")
            total_count = cur.fetchone()[0]

            if total_count > 0:
                orphan_pct = (orphan_count / total_count) * 100
                print(
                    f"  {child_table}.{fk_col} -> {parent_table}: "
                    f"{orphan_count}/{total_count} orphaned ({orphan_pct:.1f}%)"
                )

                # Some orphans are expected (deleted parents, etc.)
                # But should be less than 50%
                assert orphan_pct < 50, (
                    f"Too many orphaned records in {child_table}.{fk_col}"
                )

        except sqlite3.OperationalError as e:
            print(f"  Could not verify {child_table}.{fk_col}: {e}")

    def test_database_no_duplicate_ids(self, populated_db: Path):
        """Test that no table has duplicate Id values."""
        conn = sqlite3.connect(str(populated_db))
        try:
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]

            for table in tables:
                cur.execute(f"PRAGMA table_info([{table}])")
                columns = [col[1].lower() for col in cur.fetchall()]

                if "id" not in columns:
                    continue

                # Find actual Id column name
                cur.execute(f"PRAGMA table_info([{table}])")
                id_col = next(
                    (col[1] for col in cur.fetchall() if col[1].lower() == "id"),
                    None,
                )

                if id_col:
                    cur.execute(
                        f"""
                        SELECT [{id_col}], COUNT(*) as cnt
                        FROM [{table}]
                        GROUP BY [{id_col}]
                        HAVING cnt > 1
                        LIMIT 5
                    """
                    )
                    duplicates = cur.fetchall()

                    assert len(duplicates) == 0, (
                        f"Table {table} has duplicate Ids: {duplicates}"
                    )

        finally:
            conn.close()

    def test_database_essential_objects_present(self, populated_db: Path):
        """Test that essential objects are present in database."""
        from sfdump.orchestrator import ESSENTIAL_OBJECTS

        conn = sqlite3.connect(str(populated_db))
        try:
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0].lower() for row in cur.fetchall()]

            # Check for core objects (should always be present)
            core_objects = ["account", "contact", "opportunity", "user"]
            found_core = []
            missing_core = []

            for obj in core_objects:
                if obj.lower() in tables:
                    found_core.append(obj)
                else:
                    missing_core.append(obj)

            print(f"\nCore objects found: {found_core}")
            print(f"Core objects missing: {missing_core}")

            # At least Account should be present
            assert "account" in tables, "Account table missing from database"

            # Count how many essential objects are present
            essential_found = sum(
                1 for obj in ESSENTIAL_OBJECTS if obj.lower() in tables
            )
            print(
                f"Essential objects found: {essential_found}/{len(ESSENTIAL_OBJECTS)}"
            )

        finally:
            conn.close()
