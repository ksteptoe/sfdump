"""Tests for sfdump.analyse module."""

import csv
from pathlib import Path
from unittest.mock import MagicMock

from sfdump.analyse import (
    _load_missing,
    _safe_query_parent,
    analyse_missing_files,
    infer_object_from_id,
)


class TestInferObjectFromId:
    """Tests for infer_object_from_id function."""

    def test_account_id(self):
        """Recognizes Account ID prefix."""
        result = infer_object_from_id("001ABC123456789")
        assert result == "Account"

    def test_contact_id(self):
        """Recognizes Contact ID prefix."""
        result = infer_object_from_id("003ABC123456789")
        assert result == "Contact"

    def test_opportunity_id(self):
        """Recognizes Opportunity ID prefix."""
        result = infer_object_from_id("006ABC123456789")
        assert result == "Opportunity"

    def test_user_id(self):
        """Recognizes User ID prefix."""
        result = infer_object_from_id("005ABC123456789")
        assert result == "User"

    def test_lead_id(self):
        """Recognizes Lead ID prefix."""
        result = infer_object_from_id("00QABC123456789")
        assert result == "Lead"

    def test_case_id(self):
        """Recognizes Case ID prefix."""
        result = infer_object_from_id("500ABC123456789")
        assert result == "Case"

    def test_campaign_id(self):
        """Recognizes Campaign ID prefix."""
        result = infer_object_from_id("701ABC123456789")
        assert result == "Campaign"

    def test_custom_object_id(self):
        """Recognizes custom object ID prefix starting with 'a'."""
        result = infer_object_from_id("a02ABC123456789")
        assert result == "CustomObject"

    def test_unknown_prefix(self):
        """Returns Unknown for unrecognized prefix."""
        result = infer_object_from_id("XXXABC123456789")
        assert result == "Unknown"

    def test_empty_id(self):
        """Returns Unknown for empty ID."""
        result = infer_object_from_id("")
        assert result == "Unknown"

    def test_short_id(self):
        """Returns Unknown for ID shorter than 3 chars."""
        result = infer_object_from_id("00")
        assert result == "Unknown"

    def test_none_id(self):
        """Returns Unknown for None ID."""
        result = infer_object_from_id(None)
        assert result == "Unknown"


class TestLoadMissing:
    """Tests for _load_missing function."""

    def test_loads_existing_csv(self, tmp_path):
        """Loads existing missing files CSV."""
        csv_file = tmp_path / "missing.csv"
        csv_file.write_text("Id,ParentId,Name\nATT001,ACC001,doc.pdf\n")

        result = _load_missing(str(csv_file))

        assert len(result) == 1
        assert result[0]["Id"] == "ATT001"

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty list for non-existent file."""
        result = _load_missing(str(tmp_path / "nonexistent.csv"))

        assert result == []


class TestSafeQueryParent:
    """Tests for _safe_query_parent function."""

    def test_returns_name_field(self):
        """Returns Name field from successful query."""
        mock_api = MagicMock()
        mock_api.query.return_value = {"records": [{"Name": "Acme Corp"}]}

        result = _safe_query_parent(mock_api, "Account", "001ABC123")

        assert result == "Acme Corp"

    def test_falls_back_to_invoice_number(self):
        """Falls back to InvoiceNumber field when Name fails."""
        mock_api = MagicMock()
        # First call (Name) fails, second call (InvoiceNumber) succeeds
        mock_api.query.side_effect = [
            Exception("No Name field"),
            {"records": [{"InvoiceNumber": "INV-001"}]},
        ]

        result = _safe_query_parent(mock_api, "Invoice", "INV123")

        assert result == "INV-001"

    def test_returns_empty_on_all_failures(self):
        """Returns empty string when all queries fail."""
        mock_api = MagicMock()
        mock_api.query.side_effect = Exception("Query failed")

        result = _safe_query_parent(mock_api, "Account", "001ABC123")

        assert result == ""

    def test_returns_empty_on_no_records(self):
        """Returns empty string when no records returned."""
        mock_api = MagicMock()
        mock_api.query.return_value = {"records": []}

        result = _safe_query_parent(mock_api, "Account", "001ABC123")

        assert result == ""


class TestAnalyseMissingFiles:
    """Tests for analyse_missing_files function."""

    def test_no_missing_files(self, tmp_path):
        """Creates empty analysis when no missing files."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        mock_api = MagicMock()

        result = analyse_missing_files(str(tmp_path), mock_api)

        assert Path(result).exists()
        content = Path(result).read_text()
        assert "No missing files detected" in content

    def test_groups_by_parent(self, tmp_path):
        """Groups missing files by parent ID."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Create missing attachments CSV
        attach_csv = links_dir / "attachments_missing.csv"
        attach_csv.write_text(
            "Id,ParentId,Name\nATT001,001ABC123,doc1.pdf\nATT002,001ABC123,doc2.pdf\n"
        )

        mock_api = MagicMock()
        mock_api.query.return_value = {"records": [{"Name": "Acme Corp"}]}
        mock_api.instance_url = "https://test.salesforce.com"

        result = analyse_missing_files(str(tmp_path), mock_api)

        # Read the output CSV
        with Path(result).open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Should have one grouped row for the parent
        assert len(rows) == 1
        assert rows[0]["ParentId"] == "001ABC123"
        assert rows[0]["MissingCount"] == "2"
        assert rows[0]["ParentObject"] == "Account"

    def test_combines_attachments_and_content_versions(self, tmp_path):
        """Combines missing attachments and content versions."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Create both missing CSVs
        attach_csv = links_dir / "attachments_missing.csv"
        attach_csv.write_text("Id,ParentId,Name\nATT001,001ABC123,doc1.pdf\n")

        cv_csv = links_dir / "content_versions_missing.csv"
        cv_csv.write_text("Id,ParentId,Name\nCV001,001ABC123,doc2.pdf\n")

        mock_api = MagicMock()
        mock_api.query.return_value = {"records": [{"Name": "Acme Corp"}]}
        mock_api.instance_url = "https://test.salesforce.com"

        result = analyse_missing_files(str(tmp_path), mock_api)

        with Path(result).open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["MissingCount"] == "2"
        assert "Attachment" in rows[0]["MissingKinds"]
        assert "ContentVersion" in rows[0]["MissingKinds"]

    def test_includes_parent_record_url(self, tmp_path):
        """Includes Salesforce URL for parent record."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        attach_csv = links_dir / "attachments_missing.csv"
        attach_csv.write_text("Id,ParentId,Name\nATT001,001ABC123,doc.pdf\n")

        mock_api = MagicMock()
        mock_api.query.return_value = {"records": [{"Name": "Acme"}]}
        mock_api.instance_url = "https://myorg.salesforce.com"

        result = analyse_missing_files(str(tmp_path), mock_api)

        with Path(result).open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "https://myorg.salesforce.com/001ABC123" in rows[0]["ParentRecordUrl"]

    def test_handles_unknown_parent(self, tmp_path):
        """Handles unknown parent object type."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        attach_csv = links_dir / "attachments_missing.csv"
        attach_csv.write_text("Id,ParentId,Name\nATT001,XXXABC123,doc.pdf\n")

        mock_api = MagicMock()
        mock_api.instance_url = "https://test.salesforce.com"

        result = analyse_missing_files(str(tmp_path), mock_api)

        with Path(result).open() as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert rows[0]["ParentObject"] == "Unknown"
        assert rows[0]["ParentName"] == ""  # No query for unknown type
