"""Tests for sfdump.viewer_app.services.documents module."""

import sqlite3
from unittest.mock import patch

import pytest

from sfdump.viewer_app.services.documents import (
    _pick_first,
    _table_columns,
    list_record_documents,
    load_master_documents_index,
)


class TestPickFirst:
    """Tests for _pick_first function."""

    def test_picks_first_match(self):
        """Returns first matching candidate."""
        cols = {"a", "b", "c", "object_type"}
        candidates = ["record_api", "object_type", "api_name"]

        result = _pick_first(cols, candidates)

        assert result == "object_type"

    def test_no_match_returns_none(self):
        """Returns None when no candidates match."""
        cols = {"a", "b", "c"}
        candidates = ["x", "y", "z"]

        result = _pick_first(cols, candidates)

        assert result is None

    def test_empty_cols_returns_none(self):
        """Returns None for empty cols set."""
        result = _pick_first(set(), ["a", "b"])

        assert result is None

    def test_order_matters(self):
        """First candidate in list is preferred."""
        cols = {"a", "b", "c"}
        candidates = ["b", "a", "c"]

        result = _pick_first(cols, candidates)

        assert result == "b"


class TestTableColumns:
    """Tests for _table_columns function."""

    def test_returns_column_names(self, tmp_path):
        """Returns list of column names from table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id TEXT, name TEXT, value INTEGER)")
        conn.commit()

        result = _table_columns(conn, "test")

        assert result == ["id", "name", "value"]
        conn.close()

    def test_empty_table(self, tmp_path):
        """Returns column names even for empty table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE empty_table (col1 TEXT, col2 TEXT)")
        conn.commit()

        result = _table_columns(conn, "empty_table")

        assert result == ["col1", "col2"]
        conn.close()


class TestListRecordDocuments:
    """Tests for list_record_documents function."""

    @pytest.fixture
    def docs_db(self, tmp_path):
        """Create a test database with record_documents table."""
        db_path = tmp_path / "docs.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE record_documents (
                object_type TEXT,
                record_id TEXT,
                path TEXT,
                file_name TEXT
            )
        """)
        conn.execute("""
            INSERT INTO record_documents VALUES
            ('Account', 'ACC001', 'files/doc1.pdf', 'doc1.pdf'),
            ('Account', 'ACC001', 'files/doc2.pdf', 'doc2.pdf'),
            ('Opportunity', 'OPP001', 'files/doc3.pdf', 'doc3.pdf')
        """)
        conn.commit()
        conn.close()
        return db_path

    @patch("sfdump.viewer_app.services.documents.st")
    def test_finds_documents_for_record(self, mock_st, docs_db):
        """Finds documents for a specific record."""
        result = list_record_documents(
            db_path=docs_db,
            object_type="Account",
            record_id="ACC001",
        )

        assert len(result) == 2
        paths = {r["path"] for r in result}
        assert paths == {"files/doc1.pdf", "files/doc2.pdf"}

    @patch("sfdump.viewer_app.services.documents.st")
    def test_no_documents_for_record(self, mock_st, docs_db):
        """Returns empty list when no documents found."""
        result = list_record_documents(
            db_path=docs_db,
            object_type="Account",
            record_id="ACC999",
        )

        assert result == []

    @patch("sfdump.viewer_app.services.documents.st")
    def test_respects_limit(self, mock_st, docs_db):
        """Respects the limit parameter."""
        result = list_record_documents(
            db_path=docs_db,
            object_type="Account",
            record_id="ACC001",
            limit=1,
        )

        assert len(result) == 1

    @patch("sfdump.viewer_app.services.documents.st")
    def test_nonexistent_db_returns_empty(self, mock_st, tmp_path):
        """Returns empty list for non-existent database."""
        result = list_record_documents(
            db_path=tmp_path / "nonexistent.db",
            object_type="Account",
            record_id="ACC001",
        )

        assert result == []
        mock_st.warning.assert_called()

    @patch("sfdump.viewer_app.services.documents.st")
    def test_no_record_documents_table(self, mock_st, tmp_path):
        """Returns empty list when record_documents table doesn't exist."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id TEXT)")
        conn.close()

        result = list_record_documents(
            db_path=db_path,
            object_type="Account",
            record_id="ACC001",
        )

        assert result == []


class TestLoadMasterDocumentsIndex:
    """Tests for load_master_documents_index function."""

    @pytest.fixture
    def export_with_index(self, tmp_path):
        """Create export structure with master documents index."""
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()

        csv_content = """record_id,object_type,local_path,file_name,file_extension
ACC001,Account,files/doc1.pdf,doc1,pdf
ACC002,Account,files/doc2.docx,doc2,docx
OPP001,Opportunity,files/doc3.xlsx,doc3,xlsx
"""
        (meta_dir / "master_documents_index.csv").write_text(csv_content)
        return tmp_path

    @patch("sfdump.viewer_app.services.documents.st")
    def test_loads_csv_as_dataframe(self, mock_st, export_with_index):
        """Loads CSV and returns DataFrame."""
        result = load_master_documents_index(export_with_index)

        assert result is not None
        assert len(result) == 3
        assert "record_id" in result.columns
        assert "object_type" in result.columns

    @patch("sfdump.viewer_app.services.documents.st")
    def test_nonexistent_index_returns_none(self, mock_st, tmp_path):
        """Returns None when index file doesn't exist."""
        result = load_master_documents_index(tmp_path)

        assert result is None

    @patch("sfdump.viewer_app.services.documents.st")
    def test_column_normalization(self, mock_st, tmp_path):
        """Normalizes column names to expected format."""
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()

        # Use alternative column names
        csv_content = """linkedentityid,record_api,path,title,ext
ACC001,Account,files/doc1.pdf,doc1,pdf
"""
        (meta_dir / "master_documents_index.csv").write_text(csv_content)

        result = load_master_documents_index(tmp_path)

        assert result is not None
        # Should have normalized columns
        assert "record_id" in result.columns
        assert "object_type" in result.columns
        assert "local_path" in result.columns
