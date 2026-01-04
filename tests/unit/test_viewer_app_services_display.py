"""Tests for sfdump.viewer_app.services.display module."""

from sfdump.viewer_app.services.display import (
    IMPORTANT_FIELDS,
    get_important_fields,
    select_display_columns,
)


class TestGetImportantFields:
    """Tests for get_important_fields function."""

    def test_known_object_returns_fields(self):
        """Known objects return their configured important fields."""
        result = get_important_fields("Account")

        assert "Name" in result
        assert "Type" in result
        assert "Industry" in result

    def test_opportunity_fields(self):
        """Opportunity has expected important fields."""
        result = get_important_fields("Opportunity")

        assert "Name" in result
        assert "StageName" in result
        assert "Amount" in result
        assert "CloseDate" in result

    def test_coda_invoice_fields(self):
        """Coda invoice object has expected fields."""
        result = get_important_fields("c2g__codaInvoice__c")

        assert "Name" in result
        assert "c2g__InvoiceDate__c" in result
        assert "c2g__InvoiceStatus__c" in result

    def test_unknown_object_returns_empty_list(self):
        """Unknown objects return empty list."""
        result = get_important_fields("UnknownObject__c")

        assert result == []

    def test_most_configured_objects_have_name(self):
        """Most configured objects should have Name or Title as an important field."""
        # Line item objects don't have Name - they reference parent objects
        line_item_objects = {
            "OpportunityLineItem",
            "c2g__codaInvoiceLineItem__c",
            "c2g__codaPurchaseInvoiceLineItem__c",
            "c2g__codaJournalLineItem__c",
            "ContentDocumentLink",
        }
        for obj_name, fields in IMPORTANT_FIELDS.items():
            if obj_name in line_item_objects:
                continue
            assert "Name" in fields or "Title" in fields, f"{obj_name} missing Name/Title"


class TestSelectDisplayColumns:
    """Tests for select_display_columns function."""

    def test_show_all_fields_returns_all_columns(self):
        """When show_all_fields=True, return all columns."""

        class MockDF:
            columns = ["Id", "Name", "Extra1", "Extra2", "Extra3"]

        result = select_display_columns("Account", MockDF(), show_all_fields=True)

        assert result == ["Id", "Name", "Extra1", "Extra2", "Extra3"]

    def test_known_object_returns_important_fields(self):
        """Known objects return configured important fields that exist."""

        class MockDF:
            columns = ["Id", "Name", "Type", "Industry", "ExtraField"]

        result = select_display_columns("Account", MockDF(), show_all_fields=False)

        assert "Name" in result
        assert "Type" in result
        assert "Industry" in result
        assert "ExtraField" not in result

    def test_unknown_object_uses_heuristics(self):
        """Unknown objects fall back to heuristic column selection."""

        class MockDF:
            columns = ["Id", "Name", "Status", "Amount", "RandomField"]

        result = select_display_columns("CustomObject__c", MockDF(), show_all_fields=False)

        # Heuristics should pick common fields like Name, Status, Amount
        assert "Name" in result

    def test_show_ids_adds_id_column(self):
        """show_ids=True adds Id column if not already present."""

        class MockDF:
            columns = ["Id", "Name", "Type"]

        result = select_display_columns("Account", MockDF(), show_all_fields=False, show_ids=True)

        assert "Id" in result

    def test_backward_compat_df_only(self):
        """Backward compatibility: called with just df returns all columns."""

        class MockDF:
            columns = ["Col1", "Col2", "Col3"]

        result = select_display_columns(MockDF())

        assert result == ["Col1", "Col2", "Col3"]

    def test_none_df_returns_empty_list(self):
        """None df with string api_name returns empty list."""
        result = select_display_columns("Account", None)

        assert result == []

    def test_columns_ordered_by_original_position(self):
        """Result columns maintain original column order."""

        class MockDF:
            columns = ["Id", "Industry", "Name", "Type", "Website"]

        result = select_display_columns("Account", MockDF(), show_all_fields=False)

        # Get the indices in original order
        orig_indices = [MockDF.columns.index(c) for c in result if c in MockDF.columns]
        assert orig_indices == sorted(orig_indices), "Columns should be in original order"

    def test_fallback_to_first_8_columns(self):
        """If no heuristics match, fall back to first 8 columns."""

        class MockDF:
            columns = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

        result = select_display_columns("WeirdObject__c", MockDF(), show_all_fields=False)

        # Should have at most 8 columns when falling back
        assert len(result) <= 8
