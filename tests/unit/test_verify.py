"""Tests for sfdump.verify module."""

import hashlib

from sfdump.verify import (
    _load_csv,
    _sha256_of_file,
    _verify_rows,
    _write_csv,
    build_cfo_report,
    load_missing_csv,
    verify_attachments,
    verify_content_versions,
)


class TestSha256OfFile:
    """Tests for _sha256_of_file function."""

    def test_computes_sha256(self, tmp_path):
        """Computes correct SHA256 hash of file content."""
        test_file = tmp_path / "test.txt"
        content = b"Hello, World!"
        test_file.write_bytes(content)

        result = _sha256_of_file(str(test_file))

        expected = hashlib.sha256(content).hexdigest()
        assert result == expected

    def test_empty_file(self, tmp_path):
        """Handles empty file correctly."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")

        result = _sha256_of_file(str(test_file))

        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected

    def test_large_file(self, tmp_path):
        """Handles large file with multiple chunks."""
        test_file = tmp_path / "large.bin"
        # Create 3MB file (larger than 1MB chunk size)
        content = b"x" * (3 * 1024 * 1024)
        test_file.write_bytes(content)

        result = _sha256_of_file(str(test_file))

        expected = hashlib.sha256(content).hexdigest()
        assert result == expected


class TestLoadCsv:
    """Tests for _load_csv function."""

    def test_loads_csv_as_dicts(self, tmp_path):
        """Loads CSV into list of dicts."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name,value\n1,Alice,100\n2,Bob,200\n")

        result = _load_csv(str(csv_file))

        assert len(result) == 2
        assert result[0] == {"id": "1", "name": "Alice", "value": "100"}
        assert result[1] == {"id": "2", "name": "Bob", "value": "200"}

    def test_empty_csv(self, tmp_path):
        """Handles CSV with only headers."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("id,name,value\n")

        result = _load_csv(str(csv_file))

        assert result == []


class TestWriteCsv:
    """Tests for _write_csv function."""

    def test_writes_csv(self, tmp_path):
        """Writes rows to CSV file."""
        csv_file = tmp_path / "output.csv"
        rows = [
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ]

        _write_csv(str(csv_file), rows, ["id", "name"])

        content = csv_file.read_text()
        assert "id,name" in content
        assert "1,Alice" in content
        assert "2,Bob" in content


class TestVerifyRows:
    """Tests for _verify_rows function."""

    def test_valid_files_pass(self, tmp_path):
        """Files with correct SHA256 pass verification."""
        # Create test file
        test_file = tmp_path / "files" / "doc.pdf"
        test_file.parent.mkdir()
        content = b"test content"
        test_file.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        rows = [{"path": "files/doc.pdf", "sha256": sha}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert missing == []
        assert corrupt == []

    def test_missing_file(self, tmp_path):
        """Detects missing files."""
        rows = [{"path": "files/missing.pdf", "sha256": "abc123"}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(missing) == 1
        assert missing[0]["verify_error"] == "file-not-found"

    def test_missing_path_field(self, tmp_path):
        """Detects rows with missing path field."""
        rows = [{"sha256": "abc123"}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(missing) == 1
        assert missing[0]["verify_error"] == "missing-path-field"

    def test_empty_path_field(self, tmp_path):
        """Detects rows with empty path field."""
        rows = [{"path": "", "sha256": "abc123"}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(missing) == 1
        assert missing[0]["verify_error"] == "missing-path-field"

    def test_zero_size_file(self, tmp_path):
        """Detects zero-size files."""
        test_file = tmp_path / "empty.pdf"
        test_file.write_bytes(b"")

        rows = [{"path": "empty.pdf", "sha256": "abc123"}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(missing) == 1
        assert missing[0]["verify_error"] == "zero-size-file"

    def test_sha256_mismatch(self, tmp_path):
        """Detects files with SHA256 mismatch."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"actual content")

        rows = [{"path": "doc.pdf", "sha256": "wrong_hash"}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(corrupt) == 1
        assert corrupt[0]["verify_error"] == "sha256-mismatch"
        assert "sha256_actual" in corrupt[0]

    def test_missing_sha256_in_metadata(self, tmp_path):
        """Detects files with missing SHA256 in metadata."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"content")

        rows = [{"path": "doc.pdf", "sha256": ""}]

        missing, corrupt = _verify_rows(rows, str(tmp_path))

        assert len(corrupt) == 1
        assert corrupt[0]["verify_error"] == "sha256-missing"


class TestVerifyAttachments:
    """Tests for verify_attachments function."""

    def test_creates_missing_csv(self, tmp_path):
        """Creates missing attachments CSV when files are missing."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()
        meta_csv = links_dir / "attachments_meta.csv"
        meta_csv.write_text("Id,path,sha256\nATT001,files/missing.pdf,abc123\n")

        verify_attachments(str(meta_csv), str(tmp_path))

        missing_csv = links_dir / "attachments_missing.csv"
        assert missing_csv.exists()

    def test_creates_corrupt_csv(self, tmp_path):
        """Creates corrupt attachments CSV when SHA mismatch."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Create file with content
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        test_file = files_dir / "doc.pdf"
        test_file.write_bytes(b"content")

        meta_csv = links_dir / "attachments_meta.csv"
        meta_csv.write_text("Id,path,sha256\nATT001,files/doc.pdf,wrong_hash\n")

        verify_attachments(str(meta_csv), str(tmp_path))

        corrupt_csv = links_dir / "attachments_corrupt.csv"
        assert corrupt_csv.exists()

    def test_no_issues(self, tmp_path):
        """No CSV created when all files are valid."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        test_file = files_dir / "doc.pdf"
        content = b"content"
        test_file.write_bytes(content)
        sha = hashlib.sha256(content).hexdigest()

        meta_csv = links_dir / "attachments_meta.csv"
        meta_csv.write_text(f"Id,path,sha256\nATT001,files/doc.pdf,{sha}\n")

        verify_attachments(str(meta_csv), str(tmp_path))

        # No missing or corrupt CSVs should be created
        missing_csv = links_dir / "attachments_missing.csv"
        corrupt_csv = links_dir / "attachments_corrupt.csv"
        assert not missing_csv.exists()
        assert not corrupt_csv.exists()


class TestVerifyContentVersions:
    """Tests for verify_content_versions function."""

    def test_creates_missing_csv(self, tmp_path):
        """Creates missing content versions CSV when files are missing."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()
        meta_csv = links_dir / "content_versions_meta.csv"
        meta_csv.write_text("Id,path,sha256\nCV001,files/missing.pdf,abc123\n")

        verify_content_versions(str(meta_csv), str(tmp_path))

        missing_csv = links_dir / "content_versions_missing.csv"
        assert missing_csv.exists()


class TestLoadMissingCsv:
    """Tests for load_missing_csv function."""

    def test_loads_existing_csv(self, tmp_path):
        """Loads existing CSV file."""
        csv_file = tmp_path / "missing.csv"
        csv_file.write_text("Id,Name\nATT001,doc.pdf\nATT002,image.png\n")

        result = load_missing_csv(csv_file)

        assert len(result) == 2
        assert result[0]["Id"] == "ATT001"

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty list for non-existent file."""
        result = load_missing_csv(tmp_path / "nonexistent.csv")

        assert result == []


class TestBuildCfoReport:
    """Tests for build_cfo_report function."""

    def test_empty_report(self, tmp_path):
        """Generates report with no missing files."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        result = build_cfo_report(tmp_path)

        assert "# CFO Forensic Audit Report" in result
        assert "Missing attachments found: **0**" in result

    def test_report_with_missing_files(self, tmp_path):
        """Generates report with missing files."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        missing_csv = links_dir / "attachments_missing.csv"
        missing_csv.write_text("Id,ParentId,Name\nATT001,ACC001,doc.pdf\n")

        result = build_cfo_report(tmp_path)

        assert "Missing attachments found: **1**" in result
        assert "ATT001" in result
        assert "doc.pdf" in result

    def test_report_with_redaction(self, tmp_path):
        """Generates report with redacted names."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        missing_csv = links_dir / "attachments_missing.csv"
        missing_csv.write_text("Id,ParentId,Name\nATT001,ACC001,sensitive.pdf\n")

        result = build_cfo_report(tmp_path, redact=True)

        assert "[REDACTED]" in result
        assert "sensitive.pdf" not in result

    def test_report_with_retry_results(self, tmp_path):
        """Generates report with retry results."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        retry_csv = links_dir / "attachments_missing_retry.csv"
        retry_csv.write_text(
            "Id,retry_status,retry_error\nATT001,recovered,\nATT002,forbidden,403 Error\n"
        )

        result = build_cfo_report(tmp_path)

        assert "Files recovered on retry: **1**" in result
        assert "Still missing after retry: **1**" in result
        assert "recovered" in result
        assert "forbidden" in result
