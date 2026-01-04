"""Tests for sfdump.dumper module core functions."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock

from sfdump.dumper import (
    _dedupe_preserve_order,
    _get_by_path,
    _get_queryable_fieldnames,
    _is_polymorphic_reference,
    _move_id_first,
    _record_iter,
    _scalarize,
    dump_object_to_csv,
    fieldnames_for_object,
)


class TestMoveIdFirst:
    """Tests for _move_id_first function."""

    def test_moves_id_to_front(self):
        """Moves Id field to the front of the list."""
        fields = ["Name", "Id", "Status"]

        result = _move_id_first(fields)

        assert result == ["Id", "Name", "Status"]

    def test_no_id_returns_unchanged(self):
        """Returns unchanged list if no Id field."""
        fields = ["Name", "Status"]

        result = _move_id_first(fields)

        assert result == ["Name", "Status"]

    def test_id_already_first(self):
        """Returns list as-is if Id is already first."""
        fields = ["Id", "Name", "Status"]

        result = _move_id_first(fields)

        assert result == ["Id", "Name", "Status"]


class TestDedupePreserveOrder:
    """Tests for _dedupe_preserve_order function."""

    def test_removes_duplicates(self):
        """Removes duplicate items while preserving order."""
        items = ["a", "b", "a", "c", "b"]

        result = _dedupe_preserve_order(items)

        assert result == ["a", "b", "c"]

    def test_no_duplicates(self):
        """Returns same list if no duplicates."""
        items = ["a", "b", "c"]

        result = _dedupe_preserve_order(items)

        assert result == ["a", "b", "c"]

    def test_empty_list(self):
        """Handles empty list."""
        result = _dedupe_preserve_order([])

        assert result == []


class TestIsPolymorphicReference:
    """Tests for _is_polymorphic_reference function."""

    def test_polymorphic_reference(self):
        """Detects polymorphic references (multiple targets)."""
        fdesc = {
            "relationshipName": "What",
            "type": "reference",
            "referenceTo": ["Account", "Opportunity", "Case"],
        }

        result = _is_polymorphic_reference(fdesc)

        assert result is True

    def test_single_target_reference(self):
        """Non-polymorphic reference (single target)."""
        fdesc = {
            "relationshipName": "Account",
            "type": "reference",
            "referenceTo": ["Account"],
        }

        result = _is_polymorphic_reference(fdesc)

        assert result is False

    def test_no_relationship_name(self):
        """Not polymorphic if no relationship name."""
        fdesc = {
            "type": "reference",
            "referenceTo": ["Account", "Opportunity"],
        }

        result = _is_polymorphic_reference(fdesc)

        assert result is False

    def test_non_reference_type(self):
        """Not polymorphic if not a reference type."""
        fdesc = {
            "relationshipName": "Something",
            "type": "string",
            "referenceTo": [],
        }

        result = _is_polymorphic_reference(fdesc)

        assert result is False


class TestGetQueryableFieldnames:
    """Tests for _get_queryable_fieldnames function."""

    def test_returns_queryable_fields(self):
        """Returns names of queryable fields."""
        desc = {
            "fields": [
                {"name": "Id", "queryable": True},
                {"name": "Name", "queryable": True},
                {"name": "Formula", "queryable": False},
            ]
        }

        result = _get_queryable_fieldnames(desc)

        assert "Id" in result
        assert "Name" in result
        assert "Formula" not in result

    def test_default_queryable(self):
        """Fields without queryable default to True."""
        desc = {
            "fields": [
                {"name": "Id"},
                {"name": "Name"},
            ]
        }

        result = _get_queryable_fieldnames(desc)

        assert result == ["Id", "Name"]

    def test_empty_fields(self):
        """Handles empty fields list."""
        desc = {"fields": []}

        result = _get_queryable_fieldnames(desc)

        assert result == []


class TestGetByPath:
    """Tests for _get_by_path function."""

    def test_simple_key(self):
        """Gets value by simple key."""
        obj = {"Name": "Alice"}

        result = _get_by_path(obj, "Name")

        assert result == "Alice"

    def test_nested_path(self):
        """Gets value by nested path."""
        obj = {"Owner": {"Name": "Bob"}}

        result = _get_by_path(obj, "Owner.Name")

        assert result == "Bob"

    def test_deeply_nested(self):
        """Gets value by deeply nested path."""
        obj = {"Level1": {"Level2": {"Level3": "value"}}}

        result = _get_by_path(obj, "Level1.Level2.Level3")

        assert result == "value"

    def test_missing_key(self):
        """Returns None for missing key."""
        obj = {"Name": "Alice"}

        result = _get_by_path(obj, "Missing")

        assert result is None

    def test_missing_nested_key(self):
        """Returns None for missing nested key."""
        obj = {"Owner": {"Name": "Bob"}}

        result = _get_by_path(obj, "Owner.Email")

        assert result is None

    def test_null_intermediate(self):
        """Returns None if intermediate is None."""
        obj = {"Owner": None}

        result = _get_by_path(obj, "Owner.Name")

        assert result is None


class TestScalarize:
    """Tests for _scalarize function."""

    def test_string_unchanged(self):
        """Strings pass through unchanged."""
        result = _scalarize("hello")

        assert result == "hello"

    def test_number_unchanged(self):
        """Numbers pass through unchanged."""
        result = _scalarize(42)

        assert result == 42

    def test_dict_to_json(self):
        """Dicts are converted to JSON strings."""
        result = _scalarize({"a": 1, "b": 2})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": 2}

    def test_list_to_json(self):
        """Lists are converted to JSON strings."""
        result = _scalarize([1, 2, 3])

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_none_unchanged(self):
        """None passes through unchanged."""
        result = _scalarize(None)

        assert result is None


class TestRecordIter:
    """Tests for _record_iter function."""

    def test_iterates_records(self):
        """Iterates through all records."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {"Id": "1", "Name": "A", "attributes": {"type": "Account"}},
            {"Id": "2", "Name": "B", "attributes": {"type": "Account"}},
        ]

        result = list(_record_iter(mock_api, "SELECT Id, Name FROM Account", None))

        assert len(result) == 2
        assert result[0] == {"Id": "1", "Name": "A"}  # attributes removed
        assert result[1] == {"Id": "2", "Name": "B"}

    def test_respects_limit(self):
        """Stops after limit is reached."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {"Id": "1", "attributes": {}},
            {"Id": "2", "attributes": {}},
            {"Id": "3", "attributes": {}},
        ]

        result = list(_record_iter(mock_api, "SELECT Id FROM Account", limit=2))

        assert len(result) == 2

    def test_removes_attributes(self):
        """Removes attributes key from records."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {
                "Id": "1",
                "attributes": {"type": "Account", "url": "/services/data/v58.0/sobjects/Account/1"},
            },
        ]

        result = list(_record_iter(mock_api, "SELECT Id FROM Account", None))

        assert "attributes" not in result[0]


class TestFieldnamesForObject:
    """Tests for fieldnames_for_object function."""

    def test_basic_fields(self):
        """Returns basic queryable fields with Id first."""
        mock_api = MagicMock()
        mock_api.describe_object.return_value = {
            "fields": [
                {"name": "Name", "queryable": True, "type": "string"},
                {"name": "Id", "queryable": True, "type": "id"},
                {"name": "Status", "queryable": True, "type": "picklist"},
            ]
        }

        result = fieldnames_for_object(mock_api, "Account")

        assert result[0] == "Id"
        assert "Name" in result
        assert "Status" in result

    def test_excludes_non_queryable(self):
        """Excludes non-queryable fields."""
        mock_api = MagicMock()
        mock_api.describe_object.return_value = {
            "fields": [
                {"name": "Id", "queryable": True, "type": "id"},
                {"name": "Formula", "queryable": False, "type": "string"},
            ]
        }

        result = fieldnames_for_object(mock_api, "Account")

        assert "Id" in result
        assert "Formula" not in result


class TestDumpObjectToCsv:
    """Tests for dump_object_to_csv function."""

    def test_creates_csv_file(self, tmp_path):
        """Creates CSV file with data."""
        mock_api = MagicMock()
        mock_api.describe_object.return_value = {
            "fields": [
                {"name": "Id", "queryable": True, "type": "id"},
                {"name": "Name", "queryable": True, "type": "string"},
            ]
        }
        mock_api.query_all_iter.return_value = [
            {"Id": "001", "Name": "Acme", "attributes": {}},
            {"Id": "002", "Name": "Beta", "attributes": {}},
        ]

        csv_path, count = dump_object_to_csv(mock_api, "Account", str(tmp_path))

        assert Path(csv_path).exists()
        assert count == 2

        # Verify CSV content
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["Name"] == "Acme"

    def test_custom_fields(self, tmp_path):
        """Uses custom field list."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {"Id": "001", "Name": "Test", "attributes": {}},
        ]

        csv_path, count = dump_object_to_csv(
            mock_api, "Account", str(tmp_path), fields=["Id", "Name"]
        )

        assert count == 1
        mock_api.query_all_iter.assert_called()
        call_args = str(mock_api.query_all_iter.call_args)
        assert "Id" in call_args
        assert "Name" in call_args

    def test_with_where_clause(self, tmp_path):
        """Adds WHERE clause to query."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = []

        dump_object_to_csv(
            mock_api, "Account", str(tmp_path), fields=["Id"], where="Name LIKE 'Test%'"
        )

        call_args = str(mock_api.query_all_iter.call_args)
        assert "WHERE" in call_args
        assert "Test" in call_args

    def test_with_limit(self, tmp_path):
        """Respects limit parameter."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {"Id": "001", "attributes": {}},
            {"Id": "002", "attributes": {}},
            {"Id": "003", "attributes": {}},
        ]

        csv_path, count = dump_object_to_csv(
            mock_api, "Account", str(tmp_path), fields=["Id"], limit=2
        )

        assert count == 2

    def test_handles_nested_fields(self, tmp_path):
        """Handles dot-path fields like Owner.Name."""
        mock_api = MagicMock()
        mock_api.query_all_iter.return_value = [
            {"Id": "001", "Owner": {"Name": "Alice"}, "attributes": {}},
        ]

        csv_path, count = dump_object_to_csv(
            mock_api, "Account", str(tmp_path), fields=["Id", "Owner.Name"]
        )

        assert count == 1
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["Owner.Name"] == "Alice"
