"""Tests for sfdump.viewer_app.services.objects module."""

from dataclasses import dataclass
from unittest.mock import patch

from sfdump.viewer_app.services.objects import get_object_choices


@dataclass
class MockTable:
    """Mock table info for testing."""

    name: str


@dataclass
class MockSFObject:
    """Mock SFObject for testing."""

    api_name: str
    table_name: str
    label: str = None


class TestGetObjectChoices:
    """Tests for get_object_choices function."""

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_returns_matching_objects(self, mock_objects):
        """Returns objects that exist in the database."""
        mock_objects.values.return_value = [
            MockSFObject(api_name="Account", table_name="account", label="Account"),
            MockSFObject(api_name="Contact", table_name="contact", label="Contact"),
            MockSFObject(api_name="Lead", table_name="lead", label="Lead"),
        ]

        tables = [MockTable(name="account"), MockTable(name="contact")]

        result = get_object_choices(tables)

        assert len(result) == 2
        api_names = [r[1] for r in result]
        assert "Account" in api_names
        assert "Contact" in api_names
        assert "Lead" not in api_names

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_returns_sorted_by_label(self, mock_objects):
        """Returns choices sorted by label."""
        mock_objects.values.return_value = [
            MockSFObject(api_name="Contact", table_name="contact", label="Contact"),
            MockSFObject(api_name="Account", table_name="account", label="Account"),
        ]

        tables = [MockTable(name="account"), MockTable(name="contact")]

        result = get_object_choices(tables)

        # Should be sorted alphabetically by label
        assert result[0][1] == "Account"
        assert result[1][1] == "Contact"

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_uses_api_name_if_no_label(self, mock_objects):
        """Uses api_name as label if label is None."""
        mock_objects.values.return_value = [
            MockSFObject(api_name="CustomObject__c", table_name="custom_object__c", label=None),
        ]

        tables = [MockTable(name="custom_object__c")]

        result = get_object_choices(tables)

        assert len(result) == 1
        # Label should just be the api_name
        assert result[0][0] == "CustomObject__c"

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_formats_label_with_api_name(self, mock_objects):
        """Formats label as 'Label (api_name)' when different."""
        mock_objects.values.return_value = [
            MockSFObject(
                api_name="c2g__codaInvoice__c", table_name="c2g__codainvoice__c", label="Invoice"
            ),
        ]

        tables = [MockTable(name="c2g__codainvoice__c")]

        result = get_object_choices(tables)

        assert len(result) == 1
        assert "Invoice" in result[0][0]
        assert "c2g__codaInvoice__c" in result[0][0]

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_empty_tables(self, mock_objects):
        """Returns empty list when no tables provided."""
        mock_objects.values.return_value = [
            MockSFObject(api_name="Account", table_name="account", label="Account"),
        ]

        result = get_object_choices([])

        assert result == []

    @patch("sfdump.viewer_app.services.objects.OBJECTS")
    def test_no_matching_objects(self, mock_objects):
        """Returns empty list when no objects match tables."""
        mock_objects.values.return_value = [
            MockSFObject(api_name="Account", table_name="account", label="Account"),
        ]

        tables = [MockTable(name="other_table")]

        result = get_object_choices(tables)

        assert result == []
