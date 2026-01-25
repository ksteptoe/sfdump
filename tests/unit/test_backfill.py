"""Tests for sfdump.backfill module."""

import csv
from unittest.mock import MagicMock

from sfdump.backfill import (
    BackfillResult,
    _safe_filename,
    load_missing_from_index,
    resolve_content_version_id,
    run_backfill,
)


class TestSafeFilename:
    """Tests for _safe_filename helper."""

    def test_basic_filename(self):
        """Creates basic filename with extension."""
        result = _safe_filename("document", "pdf")
        assert result == "document.pdf"

    def test_strips_invalid_chars(self):
        """Strips invalid characters from filename."""
        result = _safe_filename("doc<>:name", "pdf")
        # Multiple invalid chars are replaced with a single underscore
        assert result == "doc_name.pdf"

    def test_empty_stem_uses_default(self):
        """Uses 'file' as default for empty stem."""
        result = _safe_filename("", "pdf")
        assert result == "file.pdf"

    def test_long_stem_truncated(self):
        """Truncates very long filenames."""
        long_name = "a" * 200
        result = _safe_filename(long_name, "pdf")
        assert len(result) <= 124  # 120 chars + ".pdf"

    def test_no_extension(self):
        """Handles missing extension."""
        result = _safe_filename("document", "")
        assert result == "document"

    def test_extension_with_dot(self):
        """Strips leading dot from extension."""
        result = _safe_filename("document", ".pdf")
        assert result == "document.pdf"


class TestLoadMissingFromIndex:
    """Tests for load_missing_from_index function."""

    def test_loads_missing_files(self, tmp_path):
        """Loads rows with file_source=File and blank local_path."""
        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,\n"
            "069DEF,doc2,pdf,File,files/06/doc2.pdf\n"
            "068GHI,doc3,docx,File,\n"
            "00P123,attach,jpg,Attachment,\n"
        )

        result = load_missing_from_index(index_path)

        assert len(result) == 2
        assert result[0]["file_id"] == "069ABC"
        assert result[1]["file_id"] == "068GHI"

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty list when file doesn't exist."""
        result = load_missing_from_index(tmp_path / "nonexistent.csv")
        assert result == []

    def test_filters_by_file_source(self, tmp_path):
        """Only returns File source, not Attachment."""
        index_path = tmp_path / "index.csv"
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,\n"
            "00PABC,attach1,jpg,Attachment,\n"
        )

        result = load_missing_from_index(index_path)

        assert len(result) == 1
        assert result[0]["file_source"] == "File"

    def test_skips_rows_with_local_path(self, tmp_path):
        """Skips rows that already have local_path filled."""
        index_path = tmp_path / "index.csv"
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,files/06/doc1.pdf\n"
            "069DEF,doc2,pdf,File,\n"
        )

        result = load_missing_from_index(index_path)

        assert len(result) == 1
        assert result[0]["file_id"] == "069DEF"

    def test_only_069_and_068_prefixes(self, tmp_path):
        """Only returns rows with 069 or 068 file_id prefixes."""
        index_path = tmp_path / "index.csv"
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,\n"
            "068DEF,doc2,pdf,File,\n"
            "070XYZ,doc3,pdf,File,\n"
        )

        result = load_missing_from_index(index_path)

        assert len(result) == 2
        assert all(r["file_id"].startswith(("069", "068")) for r in result)


class TestResolveContentVersionId:
    """Tests for resolve_content_version_id function."""

    def test_resolves_successfully(self):
        """Successfully resolves ContentDocument to ContentVersion."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"
        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068XYZ123"}
        mock_api._get.return_value = mock_response

        result = resolve_content_version_id(mock_api, "069ABC123")

        assert result == "068XYZ123"
        mock_api._get.assert_called_once()

    def test_returns_none_on_error(self):
        """Returns None when API call fails."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"
        mock_api._get.side_effect = Exception("404 Not Found")

        result = resolve_content_version_id(mock_api, "069ABC123")

        assert result is None

    def test_returns_none_when_field_missing(self):
        """Returns None when LatestPublishedVersionId not in response."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"
        mock_response = MagicMock()
        mock_response.json.return_value = {"Id": "069ABC123"}
        mock_api._get.return_value = mock_response

        result = resolve_content_version_id(mock_api, "069ABC123")

        assert result is None


class TestRunBackfill:
    """Tests for run_backfill function."""

    def test_returns_empty_when_no_index(self, tmp_path):
        """Returns zeros when master index doesn't exist."""
        mock_api = MagicMock()

        result = run_backfill(mock_api, tmp_path)

        assert result == BackfillResult(total_missing=0, downloaded=0, failed=0, skipped=0)

    def test_returns_empty_when_no_missing(self, tmp_path):
        """Returns zeros when all files have local_path."""
        mock_api = MagicMock()
        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,files/06/doc1.pdf\n"
        )

        result = run_backfill(mock_api, tmp_path)

        assert result.total_missing == 0

    def test_downloads_missing_files(self, tmp_path):
        """Successfully downloads missing files."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        # Setup: resolve returns version ID
        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response

        # Setup: download succeeds
        mock_api.download_path_to_file.return_value = 1024

        # Create index with missing file
        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n069ABC,document,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path)

        assert result.total_missing == 1
        assert result.downloaded == 1
        assert result.failed == 0
        mock_api.download_path_to_file.assert_called_once()

    def test_respects_limit(self, tmp_path):
        """Respects limit parameter."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response
        mock_api.download_path_to_file.return_value = 1024

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,\n"
            "069DEF,doc2,pdf,File,\n"
            "069GHI,doc3,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path, limit=2)

        assert result.total_missing == 3
        assert result.downloaded == 2
        assert mock_api.download_path_to_file.call_count == 2

    def test_dry_run_no_downloads(self, tmp_path):
        """Dry run doesn't download files."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n069ABC,document,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path, dry_run=True)

        assert result.downloaded == 0
        mock_api.download_path_to_file.assert_not_called()

    def test_skips_existing_files(self, tmp_path):
        """Skips files that already exist on disk."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response

        # Create index with missing file
        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n069ABC,document,pdf,File,\n"
        )

        # Pre-create the file
        files_dir = tmp_path / "files" / "06"
        files_dir.mkdir(parents=True)
        (files_dir / "069ABC_document.pdf").write_bytes(b"existing content")

        result = run_backfill(mock_api, tmp_path)

        assert result.skipped == 1
        assert result.downloaded == 0
        mock_api.download_path_to_file.assert_not_called()

    def test_updates_index_with_new_paths(self, tmp_path):
        """Updates master_documents_index.csv with new local_path values."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response
        mock_api.download_path_to_file.return_value = 1024

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n069ABC,document,pdf,File,\n"
        )

        run_backfill(mock_api, tmp_path)

        # Read back the index
        with index_path.open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["local_path"] != ""
        assert "files" in rows[0]["local_path"]

    def test_handles_download_errors(self, tmp_path):
        """Handles individual download failures without stopping."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response

        # First download fails, second succeeds
        mock_api.download_path_to_file.side_effect = [
            Exception("Network error"),
            1024,
        ]

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n"
            "069ABC,doc1,pdf,File,\n"
            "069DEF,doc2,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path)

        assert result.failed == 1
        assert result.downloaded == 1

    def test_progress_callback_called(self, tmp_path):
        """Progress callback is called at intervals."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"

        mock_response = MagicMock()
        mock_response.json.return_value = {"LatestPublishedVersionId": "068VER123"}
        mock_api._get.return_value = mock_response
        mock_api.download_path_to_file.return_value = 1024

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        # Create 5 missing files
        rows = "file_id,file_name,file_extension,file_source,local_path\n"
        for i in range(5):
            rows += f"069AB{i},doc{i},pdf,File,\n"
        index_path.write_text(rows)

        callback_calls = []

        def progress_cb(processed, total, downloaded, failed):
            callback_calls.append((processed, total, downloaded, failed))

        run_backfill(mock_api, tmp_path, progress_callback=progress_cb, progress_interval=2)

        # Should be called at 2, 4, and 5 (final)
        assert len(callback_calls) >= 2

    def test_handles_068_ids_directly(self, tmp_path):
        """Handles 068 ContentVersion IDs without resolution."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"
        mock_api.download_path_to_file.return_value = 1024

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n068ABC,document,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path)

        assert result.downloaded == 1
        # Should not call _get for resolution since ID is already 068
        mock_api._get.assert_not_called()

    def test_handles_resolution_failure(self, tmp_path):
        """Counts as failed when ContentDocument resolution fails."""
        mock_api = MagicMock()
        mock_api.api_version = "v60.0"
        mock_api.instance_url = "https://example.salesforce.com"
        mock_api._get.side_effect = Exception("404 Not Found")

        index_path = tmp_path / "meta" / "master_documents_index.csv"
        index_path.parent.mkdir(parents=True)
        index_path.write_text(
            "file_id,file_name,file_extension,file_source,local_path\n069ABC,document,pdf,File,\n"
        )

        result = run_backfill(mock_api, tmp_path)

        assert result.failed == 1
        assert result.downloaded == 0
