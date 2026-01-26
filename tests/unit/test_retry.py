"""Tests for sfdump.retry module."""

import csv
from unittest.mock import MagicMock, patch

from sfdump.retry import (
    _write_retry_results,
    load_missing_csv,
    merge_recovered_into_metadata,
    retry_missing_attachments,
    retry_missing_content_versions,
)


class TestLoadMissingCsv:
    """Tests for load_missing_csv function."""

    def test_loads_existing_csv(self, tmp_path):
        """Loads existing CSV file."""
        csv_file = tmp_path / "missing.csv"
        csv_file.write_text("Id,path,sha256\nATT001,files/doc.pdf,abc123\n")

        result = load_missing_csv(str(csv_file))

        assert len(result) == 1
        assert result[0]["Id"] == "ATT001"
        assert result[0]["path"] == "files/doc.pdf"

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty list for non-existent file."""
        result = load_missing_csv(str(tmp_path / "nonexistent.csv"))

        assert result == []

    def test_empty_csv(self, tmp_path):
        """Handles empty CSV with only headers."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("Id,path,sha256\n")

        result = load_missing_csv(str(csv_file))

        assert result == []


class TestWriteRetryResults:
    """Tests for _write_retry_results function."""

    def test_writes_csv(self, tmp_path):
        """Writes retry results to CSV."""
        csv_file = tmp_path / "retry.csv"
        rows = [
            {"Id": "ATT001", "retry_status": "recovered"},
            {"Id": "ATT002", "retry_status": "forbidden"},
        ]

        _write_retry_results(str(csv_file), rows, ["Id", "retry_status"])

        assert csv_file.exists()
        content = csv_file.read_text()
        assert "Id,retry_status" in content
        assert "ATT001,recovered" in content
        assert "ATT002,forbidden" in content


class TestRetryMissingAttachments:
    """Tests for retry_missing_attachments function."""

    def test_empty_rows_does_not_crash(self, tmp_path):
        """Handles empty rows list without crashing."""
        mock_api = MagicMock()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Should not raise an exception
        retry_missing_attachments(mock_api, [], str(tmp_path), str(links_dir))

        # No retry CSV should be created for empty input
        retry_csv = links_dir / "attachments_missing_retry.csv"
        assert not retry_csv.exists()

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)  # Disable tqdm
    def test_successful_retry(self, tmp_path):
        """Successfully retries and recovers file."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.return_value = None

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "ATT001", "path": "files/doc.pdf"}]

        retry_missing_attachments(mock_api, rows, str(tmp_path), str(links_dir))

        # Check retry CSV was created
        retry_csv = links_dir / "attachments_missing_retry.csv"
        assert retry_csv.exists()

        # Check content
        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert len(results) == 1
        assert results[0]["retry_status"] == "recovered"

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_forbidden_error(self, tmp_path):
        """Handles 403 forbidden error."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.side_effect = Exception("403 Forbidden")

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "ATT001", "path": "files/doc.pdf"}]

        retry_missing_attachments(mock_api, rows, str(tmp_path), str(links_dir))

        retry_csv = links_dir / "attachments_missing_retry.csv"
        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert results[0]["retry_status"] == "forbidden"

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_not_found_error(self, tmp_path):
        """Handles 404 not found error."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.side_effect = Exception("404 Not Found")

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "ATT001", "path": "files/doc.pdf"}]

        retry_missing_attachments(mock_api, rows, str(tmp_path), str(links_dir))

        retry_csv = links_dir / "attachments_missing_retry.csv"
        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert results[0]["retry_status"] == "not-found"

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_connection_error(self, tmp_path):
        """Handles connection error."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.side_effect = Exception("Connection refused")

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "ATT001", "path": "files/doc.pdf"}]

        retry_missing_attachments(mock_api, rows, str(tmp_path), str(links_dir))

        retry_csv = links_dir / "attachments_missing_retry.csv"
        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert results[0]["retry_status"] == "connection-error"

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_invalid_path(self, tmp_path):
        """Handles rows with missing path."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"

        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "ATT001", "path": ""}]

        retry_missing_attachments(mock_api, rows, str(tmp_path), str(links_dir))

        retry_csv = links_dir / "attachments_missing_retry.csv"
        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert results[0]["retry_status"] == "invalid-path"


class TestRetryMissingContentVersions:
    """Tests for retry_missing_content_versions function."""

    def test_empty_rows_does_not_crash(self, tmp_path):
        """Handles empty rows list without crashing."""
        mock_api = MagicMock()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Should not raise an exception
        retry_missing_content_versions(mock_api, [], str(tmp_path), str(links_dir))

        # No retry CSV should be created for empty input
        retry_csv = links_dir / "content_versions_missing_retry.csv"
        assert not retry_csv.exists()

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_successful_retry(self, tmp_path):
        """Successfully retries and recovers content version."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.return_value = None

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "CV001", "path": "files/doc.pdf"}]

        retry_missing_content_versions(mock_api, rows, str(tmp_path), str(links_dir))

        retry_csv = links_dir / "content_versions_missing_retry.csv"
        assert retry_csv.exists()

        with retry_csv.open() as f:
            reader = csv.DictReader(f)
            results = list(reader)
        assert len(results) == 1
        assert results[0]["retry_status"] == "recovered"

    @patch("sfdump.retry.tqdm", lambda x, **kwargs: x)
    def test_uses_correct_url(self, tmp_path):
        """Uses correct VersionData URL for ContentVersion."""
        mock_api = MagicMock()
        mock_api.api_version = "v58.0"
        mock_api.download_path_to_file.return_value = None

        files_dir = tmp_path / "files"
        files_dir.mkdir()
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        rows = [{"Id": "CV001", "path": "files/doc.pdf"}]

        retry_missing_content_versions(mock_api, rows, str(tmp_path), str(links_dir))

        # Check the URL used
        call_args = mock_api.download_path_to_file.call_args
        assert "/sobjects/ContentVersion/CV001/VersionData" in call_args[0][0]


class TestMergeRecoveredIntoMetadata:
    """Tests for merge_recovered_into_metadata function."""

    def test_merges_recovered_paths(self, tmp_path):
        """Successfully merges recovered paths into original metadata."""
        # Create original metadata with empty path
        original_csv = tmp_path / "attachments.csv"
        original_csv.write_text(
            "Id,path,sha256\nATT001,,abc123\nATT002,files/existing.pdf,def456\n"
        )

        # Create retry results with recovered file
        retry_csv = tmp_path / "attachments_missing_retry.csv"
        retry_csv.write_text("Id,path,retry_status\nATT001,files/recovered.pdf,recovered\n")

        count = merge_recovered_into_metadata(str(original_csv), str(retry_csv))

        assert count == 1

        # Verify original was updated
        with original_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["Id"] == "ATT001"
        assert rows[0]["path"] == "files/recovered.pdf"
        assert rows[1]["Id"] == "ATT002"
        assert rows[1]["path"] == "files/existing.pdf"  # Unchanged

    def test_does_not_overwrite_existing_paths(self, tmp_path):
        """Does not overwrite paths that already exist."""
        original_csv = tmp_path / "attachments.csv"
        original_csv.write_text("Id,path,sha256\nATT001,files/original.pdf,abc123\n")

        retry_csv = tmp_path / "retry.csv"
        retry_csv.write_text("Id,path,retry_status\nATT001,files/recovered.pdf,recovered\n")

        count = merge_recovered_into_metadata(str(original_csv), str(retry_csv))

        assert count == 0  # No updates because path already exists

        with original_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["path"] == "files/original.pdf"  # Unchanged

    def test_skips_non_recovered_status(self, tmp_path):
        """Only merges files with 'recovered' status."""
        original_csv = tmp_path / "attachments.csv"
        original_csv.write_text("Id,path,sha256\nATT001,,abc123\nATT002,,def456\n")

        retry_csv = tmp_path / "retry.csv"
        retry_csv.write_text(
            "Id,path,retry_status\n"
            "ATT001,files/doc1.pdf,recovered\n"
            "ATT002,files/doc2.pdf,forbidden\n"
        )

        count = merge_recovered_into_metadata(str(original_csv), str(retry_csv))

        assert count == 1  # Only ATT001 was merged

        with original_csv.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["path"] == "files/doc1.pdf"  # Updated
        assert rows[1]["path"] == ""  # Not updated (forbidden status)

    def test_returns_zero_for_missing_files(self, tmp_path):
        """Returns 0 when files don't exist."""
        count = merge_recovered_into_metadata(
            str(tmp_path / "nonexistent.csv"),
            str(tmp_path / "also_nonexistent.csv"),
        )

        assert count == 0

    def test_returns_zero_when_no_recovered(self, tmp_path):
        """Returns 0 when no files were recovered."""
        original_csv = tmp_path / "attachments.csv"
        original_csv.write_text("Id,path,sha256\nATT001,,abc123\n")

        retry_csv = tmp_path / "retry.csv"
        retry_csv.write_text("Id,path,retry_status\nATT001,files/doc.pdf,forbidden\n")

        count = merge_recovered_into_metadata(str(original_csv), str(retry_csv))

        assert count == 0
