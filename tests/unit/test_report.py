"""Tests for sfdump.report module."""

from pathlib import Path

import pytest

from sfdump.report import (
    _load_csv,
    _make_redaction_maps,
    _markdown_header,
    _markdown_section,
    _markdown_table,
    generate_missing_report,
)


class TestMarkdownHeader:
    """Tests for _markdown_header function."""

    def test_creates_header(self):
        """Creates markdown header."""
        result = _markdown_header("My Title")

        assert result == "# My Title\n\n"


class TestMarkdownSection:
    """Tests for _markdown_section function."""

    def test_creates_section(self):
        """Creates markdown section header."""
        result = _markdown_section("Section Title")

        assert result == "\n## Section Title\n\n"


class TestMarkdownTable:
    """Tests for _markdown_table function."""

    def test_creates_table(self):
        """Creates markdown table."""
        headers = ["Col1", "Col2"]
        rows = [["a", "b"], ["c", "d"]]

        result = _markdown_table(headers, rows)

        assert "| Col1 | Col2 |" in result
        assert "| --- | --- |" in result
        assert "| a | b |" in result
        assert "| c | d |" in result

    def test_empty_table(self):
        """Creates table with no rows."""
        headers = ["Col1", "Col2"]
        rows = []

        result = _markdown_table(headers, rows)

        assert "| Col1 | Col2 |" in result
        assert "| --- | --- |" in result


class TestLoadCsv:
    """Tests for _load_csv function."""

    def test_loads_existing_csv(self, tmp_path):
        """Loads existing CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Alice\n2,Bob\n")

        result = _load_csv(str(csv_file))

        assert len(result) == 2
        assert result[0]["id"] == "1"

    def test_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty list for non-existent file."""
        result = _load_csv(str(tmp_path / "nonexistent.csv"))

        assert result == []


class TestMakeRedactionMaps:
    """Tests for _make_redaction_maps function."""

    def test_creates_attachment_map(self):
        """Creates attachment ID to pseudonym map."""
        retry_rows = [
            {"Id": "ATT001"},
            {"Id": "ATT002"},
        ]
        analysis = []

        att_map, parent_map = _make_redaction_maps(retry_rows, analysis)

        assert att_map["ATT001"] == "ATTACHMENT_1"
        assert att_map["ATT002"] == "ATTACHMENT_2"

    def test_creates_parent_map(self):
        """Creates parent ID to pseudonym map."""
        retry_rows = []
        analysis = [
            {"ParentId": "001ABC"},
            {"ParentId": "006XYZ"},
        ]

        att_map, parent_map = _make_redaction_maps(retry_rows, analysis)

        assert parent_map["001ABC"] == "PARENT_1"
        assert parent_map["006XYZ"] == "PARENT_2"

    def test_deduplicates_ids(self):
        """Does not duplicate IDs in maps."""
        retry_rows = [
            {"Id": "ATT001"},
            {"Id": "ATT001"},  # duplicate
        ]
        analysis = []

        att_map, parent_map = _make_redaction_maps(retry_rows, analysis)

        # Should only have one entry
        assert len([k for k in att_map if k.startswith("ATT")]) == 1


class TestGenerateMissingReport:
    """Tests for generate_missing_report function."""

    @pytest.fixture
    def export_structure(self, tmp_path):
        """Create export directory structure with test data."""
        links_dir = tmp_path / "links"
        links_dir.mkdir()

        # Create metadata CSVs
        (links_dir / "attachments.csv").write_text(
            "Id,Name,ParentId\nATT001,doc1.pdf,001ABC\nATT002,doc2.pdf,001ABC\n"
        )
        (links_dir / "content_versions.csv").write_text("Id,Title\nCV001,file1.pdf\n")

        return tmp_path

    def test_creates_markdown_report(self, export_structure):
        """Creates markdown report file."""
        md_path, pdf_path = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        assert Path(md_path).exists()
        assert md_path.endswith(".md")
        assert pdf_path is None

    def test_report_contains_summary(self, export_structure):
        """Report contains executive summary."""
        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()

        assert "Executive Summary" in content
        assert "Attachments" in content
        assert "Content Versions" in content

    def test_report_with_missing_files(self, export_structure):
        """Report includes missing files data."""
        links_dir = export_structure / "links"
        (links_dir / "attachments_missing.csv").write_text(
            "Id,Name,ParentId\nATT003,missing.pdf,001ABC\n"
        )

        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()
        assert "Missing or unrecoverable" in content

    def test_report_with_retry_data(self, export_structure):
        """Report includes retry results."""
        links_dir = export_structure / "links"
        (links_dir / "attachments_missing_retry.csv").write_text(
            "Id,Name,ParentId,retry_success,retry_status,retry_error\n"
            "ATT001,doc.pdf,001ABC,false,forbidden,403 Error\n"
        )

        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()
        assert "Diagnostic Evidence" in content
        assert "forbidden" in content

    def test_report_with_redaction(self, export_structure):
        """Report redacts sensitive data when requested."""
        links_dir = export_structure / "links"
        (links_dir / "attachments_missing_retry.csv").write_text(
            "Id,Name,ParentId,retry_success\nATT001,sensitive_doc.pdf,001ABC,false\n"
        )
        (links_dir / "missing_file_analysis.csv").write_text(
            "ParentId,ParentObject,ParentName,MissingCount,ParentRecordUrl\n"
            "001ABC,Account,Acme Secret Corp,1,https://test.salesforce.com/001ABC\n"
        )

        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report", redact=True
        )

        content = Path(md_path).read_text()
        assert "[REDACTED]" in content
        assert "sensitive_doc.pdf" not in content
        assert "ATTACHMENT_1" in content

    def test_report_with_analysis_data(self, export_structure):
        """Report includes impact analysis."""
        links_dir = export_structure / "links"
        (links_dir / "missing_file_analysis.csv").write_text(
            "ParentId,ParentObject,ParentName,MissingCount,ParentRecordUrl\n"
            "001ABC,Account,Acme Corp,2,https://test.salesforce.com/001ABC\n"
        )

        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()
        assert "Impact on Parent Records" in content
        assert "Account" in content

    def test_default_output_path(self, export_structure):
        """Uses default timestamp-based output path."""
        md_path, _ = generate_missing_report(str(export_structure), pdf=False)

        assert "missing_file_report-" in md_path
        assert Path(md_path).exists()

    def test_percentage_calculation(self, export_structure):
        """Calculates percentages correctly."""
        links_dir = export_structure / "links"
        # 2 attachments total, 1 missing = 50% success
        (links_dir / "attachments_missing.csv").write_text(
            "Id,Name,ParentId\nATT001,missing.pdf,001ABC\n"
        )

        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()
        assert "50.00%" in content

    def test_includes_export_context(self, export_structure):
        """Report includes export context information."""
        md_path, _ = generate_missing_report(
            str(export_structure), pdf=False, out_basename="test_report"
        )

        content = Path(md_path).read_text()
        assert "Export Context" in content
        assert "Export directory" in content

    def test_pdf_generation_skipped_without_pypandoc(self, export_structure):
        """PDF generation is skipped if pypandoc import fails."""
        # Just test that PDF generation doesn't crash when pypandoc isn't available
        # The actual PDF test requires pypandoc to be installed
        md_path, pdf_path = generate_missing_report(
            str(export_structure), pdf=True, out_basename="test_report"
        )

        # Markdown should always be created
        assert Path(md_path).exists()
        # PDF may or may not be created depending on pypandoc availability
