"""Tests for sfdump.viewer_app.services.content module."""

import sqlite3

import pytest

from sfdump.viewer_app.services.content import enrich_contentdocument_links_with_title


class MockDataFrame:
    """Mock DataFrame for testing without pandas dependency."""

    def __init__(self, data: dict):
        self._data = data
        self.columns = list(data.keys())

    def __getitem__(self, key):
        return self._data[key]

    def copy(self):
        return MockDataFrame(self._data.copy())


class TestEnrichContentdocumentLinksWithTitle:
    """Tests for enrich_contentdocument_links_with_title function."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test SQLite database with content_document table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE content_document (
                Id TEXT PRIMARY KEY,
                Title TEXT
            )
        """)
        conn.execute("INSERT INTO content_document VALUES ('DOC001', 'Document One')")
        conn.execute("INSERT INTO content_document VALUES ('DOC002', 'Document Two')")
        conn.commit()
        conn.close()
        return db_path

    def test_enriches_with_title_using_pandas(self, test_db):
        """Adds DocumentTitle column from content_document lookup."""
        pytest.importorskip("pandas")
        import pandas as pd

        df = pd.DataFrame(
            {
                "Id": ["LINK001", "LINK002"],
                "ContentDocumentId": ["DOC001", "DOC002"],
            }
        )

        result = enrich_contentdocument_links_with_title(test_db, df)

        assert result is not None
        assert "DocumentTitle" in result.columns
        assert result["DocumentTitle"].iloc[0] == "Document One"
        assert result["DocumentTitle"].iloc[1] == "Document Two"

    def test_returns_original_if_no_contentdocumentid_column(self, test_db):
        """Returns original df if ContentDocumentId column missing."""
        df = MockDataFrame(
            {
                "Id": ["LINK001"],
                "OtherColumn": ["value"],
            }
        )

        result = enrich_contentdocument_links_with_title(test_db, df)

        assert result is df  # Same object returned

    def test_returns_original_if_no_columns_attr(self, test_db):
        """Returns original object if it doesn't have columns attribute."""
        not_a_df = {"some": "dict"}

        result = enrich_contentdocument_links_with_title(test_db, not_a_df)

        assert result is not_a_df

    def test_returns_original_if_empty_ids(self, test_db):
        """Returns original df if ContentDocumentId values are empty."""
        df = MockDataFrame(
            {
                "Id": ["LINK001"],
                "ContentDocumentId": [""],
            }
        )

        result = enrich_contentdocument_links_with_title(test_db, df)

        assert result is df

    def test_handles_db_error(self, tmp_path):
        """Returns original df if database query fails."""
        # Non-existent database
        db_path = tmp_path / "nonexistent.db"

        df = MockDataFrame(
            {
                "Id": ["LINK001"],
                "ContentDocumentId": ["DOC001"],
            }
        )

        result = enrich_contentdocument_links_with_title(db_path, df)

        assert result is df

    def test_handles_missing_table(self, tmp_path):
        """Returns original df if content_document table doesn't exist."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE other_table (id TEXT)")
        conn.close()

        df = MockDataFrame(
            {
                "Id": ["LINK001"],
                "ContentDocumentId": ["DOC001"],
            }
        )

        result = enrich_contentdocument_links_with_title(db_path, df)

        assert result is df
