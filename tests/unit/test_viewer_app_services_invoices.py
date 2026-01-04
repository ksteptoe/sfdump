"""Tests for sfdump.viewer_app.services.invoices module."""

import sqlite3

import pytest

from sfdump.viewer_app.services.invoices import (
    _candidate_fk_fields,
    _looks_like_name_field,
    _select_existing,
    _table_columns,
    _table_exists,
    find_invoices_for_opportunity,
    list_invoices_for_account,
)


class TestCandidateFkFields:
    """Tests for _candidate_fk_fields function."""

    def test_exact_opportunityid_match(self):
        """Exact 'OpportunityId' is detected."""
        cols = ["Id", "Name", "OpportunityId", "Amount"]
        result = _candidate_fk_fields(cols)

        assert "OpportunityId" in result

    def test_opportunity__c_match(self):
        """Custom field 'Opportunity__c' is detected."""
        cols = ["Id", "Name", "Opportunity__c"]
        result = _candidate_fk_fields(cols)

        assert "Opportunity__c" in result

    def test_partial_match_with_suffix(self):
        """Fields containing 'opportunity' with id suffix are detected."""
        cols = ["Id", "CustomOpportunityId", "RelatedOpportunity__c"]
        result = _candidate_fk_fields(cols)

        assert "CustomOpportunityId" in result
        assert "RelatedOpportunity__c" in result

    def test_no_opportunity_fields(self):
        """Returns empty when no opportunity FK fields present."""
        cols = ["Id", "Name", "AccountId", "Status"]
        result = _candidate_fk_fields(cols)

        assert result == []

    def test_preferred_fields_ordered_first(self):
        """Standard fields like OpportunityId are ordered before custom ones."""
        cols = ["CustomOpportunityId", "OpportunityId", "MyOpportunity__c"]
        result = _candidate_fk_fields(cols)

        # OpportunityId should come first (preferred)
        assert result[0] == "OpportunityId"


class TestSelectExisting:
    """Tests for _select_existing function."""

    def test_filters_to_existing_columns(self):
        """Only returns columns that exist in the list."""
        cols = ["Id", "Name", "Status"]
        wanted = ["Id", "Name", "Amount", "CloseDate"]

        result = _select_existing(cols, wanted)

        assert result == ["Id", "Name"]

    def test_empty_cols_returns_empty(self):
        """Empty cols returns empty list."""
        result = _select_existing([], ["Id", "Name"])

        assert result == []

    def test_no_matches_returns_empty(self):
        """No matches returns empty list."""
        cols = ["A", "B", "C"]
        wanted = ["X", "Y", "Z"]

        result = _select_existing(cols, wanted)

        assert result == []


class TestLooksLikeNameField:
    """Tests for _looks_like_name_field function."""

    def test_name_field_detected(self):
        """Fields containing 'name' are detected."""
        assert _looks_like_name_field("Name") is True
        assert _looks_like_name_field("AccountName") is True
        assert _looks_like_name_field("c2g__AccountName__c") is True

    def test_id_suffix_excluded(self):
        """Fields ending in 'id' are not name fields."""
        assert _looks_like_name_field("NameId") is False
        assert _looks_like_name_field("AccountNameId") is False

    def test_non_name_fields(self):
        """Non-name fields return False."""
        assert _looks_like_name_field("Status") is False
        assert _looks_like_name_field("Amount") is False
        assert _looks_like_name_field("AccountId") is False


class TestTableExistsAndColumns:
    """Tests for _table_exists and _table_columns with real SQLite."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test SQLite database."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE c2g__codaInvoice__c (
                Id TEXT PRIMARY KEY,
                Name TEXT,
                c2g__InvoiceDate__c TEXT,
                c2g__InvoiceStatus__c TEXT,
                OpportunityId TEXT
            )
        """)
        cur.execute("""
            INSERT INTO c2g__codaInvoice__c VALUES
            ('INV001', 'Invoice 1', '2024-01-01', 'Draft', 'OPP001')
        """)
        conn.commit()
        conn.close()
        return db_path

    def test_table_exists_true(self, test_db):
        """Returns True for existing table."""
        conn = sqlite3.connect(str(test_db))
        cur = conn.cursor()

        result = _table_exists(cur, "c2g__codaInvoice__c")

        assert result is True
        conn.close()

    def test_table_exists_false(self, test_db):
        """Returns False for non-existing table."""
        conn = sqlite3.connect(str(test_db))
        cur = conn.cursor()

        result = _table_exists(cur, "NonExistentTable")

        assert result is False
        conn.close()

    def test_table_columns(self, test_db):
        """Returns list of column names."""
        conn = sqlite3.connect(str(test_db))
        cur = conn.cursor()

        result = _table_columns(cur, "c2g__codaInvoice__c")

        assert "Id" in result
        assert "Name" in result
        assert "OpportunityId" in result
        conn.close()


class TestFindInvoicesForOpportunity:
    """Tests for find_invoices_for_opportunity function."""

    @pytest.fixture
    def invoice_db(self, tmp_path):
        """Create a test database with invoice data."""
        db_path = tmp_path / "invoices.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Create invoice header table with OpportunityId FK
        cur.execute("""
            CREATE TABLE c2g__codaInvoice__c (
                Id TEXT PRIMARY KEY,
                Name TEXT,
                c2g__InvoiceDate__c TEXT,
                c2g__InvoiceStatus__c TEXT,
                c2g__InvoiceTotal__c REAL,
                OpportunityId TEXT
            )
        """)

        cur.execute("""
            INSERT INTO c2g__codaInvoice__c VALUES
            ('INV001', 'Invoice 1', '2024-01-01', 'Posted', 1000.0, 'OPP001'),
            ('INV002', 'Invoice 2', '2024-02-01', 'Draft', 2000.0, 'OPP001'),
            ('INV003', 'Invoice 3', '2024-03-01', 'Posted', 3000.0, 'OPP002')
        """)

        conn.commit()
        conn.close()
        return db_path

    def test_finds_invoices_by_opportunity_fk(self, invoice_db):
        """Finds invoices linked via OpportunityId FK."""
        rows, strategy = find_invoices_for_opportunity(invoice_db, "OPP001")

        assert strategy == "opp-fk"
        assert len(rows) == 2
        ids = {r["Id"] for r in rows}
        assert ids == {"INV001", "INV002"}

    def test_no_invoices_for_opportunity(self, invoice_db):
        """Returns empty for opportunity with no invoices."""
        rows, strategy = find_invoices_for_opportunity(invoice_db, "OPP999")

        assert strategy == "none"
        assert rows == []

    def test_no_invoice_tables(self, tmp_path):
        """Returns no-table when no invoice tables exist."""
        db_path = tmp_path / "empty.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE SomeOtherTable (Id TEXT)")
        conn.close()

        rows, strategy = find_invoices_for_opportunity(db_path, "OPP001")

        assert strategy == "no-table"
        assert rows == []


class TestListInvoicesForAccount:
    """Tests for list_invoices_for_account function."""

    @pytest.fixture
    def account_invoice_db(self, tmp_path):
        """Create a test database with account-linked invoices."""
        db_path = tmp_path / "acc_invoices.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE c2g__codaInvoice__c (
                Id TEXT PRIMARY KEY,
                Name TEXT,
                c2g__InvoiceDate__c TEXT,
                c2g__InvoiceStatus__c TEXT,
                AccountId TEXT,
                c2g__AccountName__c TEXT
            )
        """)

        cur.execute("""
            INSERT INTO c2g__codaInvoice__c VALUES
            ('INV001', 'Invoice 1', '2024-01-01', 'Posted', 'ACC001', 'Acme Corp'),
            ('INV002', 'Invoice 2', '2024-02-01', 'Draft', 'ACC001', 'Acme Corp'),
            ('INV003', 'Invoice 3', '2024-03-01', 'Posted', 'ACC002', 'Other Inc')
        """)

        conn.commit()
        conn.close()
        return db_path

    def test_finds_invoices_by_account_id(self, account_invoice_db):
        """Finds invoices by AccountId."""
        rows, strategy = list_invoices_for_account(account_invoice_db, account_id="ACC001")

        assert strategy == "account-fk"
        assert len(rows) == 2

    def test_finds_invoices_by_account_name(self, account_invoice_db):
        """Finds invoices by account name field."""
        rows, strategy = list_invoices_for_account(account_invoice_db, account_name="Acme Corp")

        assert strategy == "account-fk"
        assert len(rows) == 2

    def test_no_account_params_returns_none(self, account_invoice_db):
        """Returns none strategy when no account params provided."""
        rows, strategy = list_invoices_for_account(account_invoice_db)

        assert strategy == "none"
        assert rows == []
