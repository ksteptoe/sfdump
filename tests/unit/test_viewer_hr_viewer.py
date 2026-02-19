"""Tests for sfdump.viewer_app.ui.hr_viewer module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from sfdump.viewer_app.ui.hr_viewer import (
    _COMMON_FIELDS,
    _CONTRACTOR_EXTRA_FIELDS,
    _CONTRACTOR_RT_ID,
    _DETAIL_FIELDS,
    _EMPLOYEE_EXTRA_FIELDS,
    _EMPLOYEE_RT_ID,
    _FILTER_FIELDS,
    _count_by_type,
    _get_available_columns,
    _has_record_type_table,
    _load_contact_detail,
    _load_contacts,
    _load_regions,
    _name_variants,
)


@pytest.fixture()
def hr_db(tmp_path: Path) -> Path:
    """Create a SQLite database with contact and record_type tables for testing."""
    db_path = tmp_path / "sfdata.db"
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Create contact table with HR-relevant columns
    cur.execute("""
        CREATE TABLE contact (
            Id TEXT PRIMARY KEY,
            Name TEXT,
            FirstName TEXT,
            LastName TEXT,
            RecordTypeId TEXT,
            Title TEXT,
            Department TEXT,
            Email TEXT,
            Phone TEXT,
            MobilePhone TEXT,
            Known_As__c TEXT,
            Personal_Email_Address__c TEXT,
            Comments_Hiring__c TEXT,
            Son_Comments_HR__c TEXT,
            Son_Salary__c TEXT,
            Current_salary__c TEXT,
            Son_Employment_Type__c TEXT,
            Employment_Status__c TEXT,
            Grade__c TEXT,
            Resource_Role__c TEXT,
            Confirmed_Start_Date__c TEXT,
            Effective_End_Date__c TEXT,
            ContractRenewalDate__c TEXT,
            Son_Hiring_Status__c TEXT,
            Fixed_compensation_Local__c TEXT,
            Variable_compensation_OTE__c TEXT,
            Location__c TEXT,
            Nationality__c TEXT,
            Active__c TEXT,
            MailingCity TEXT,
            MailingCountry TEXT,
            Region__c TEXT
        )
    """)

    # Insert employees
    employees = [
        (
            "EMP001",
            "Alice Smith",
            "Alice",
            "Smith",
            _EMPLOYEE_RT_ID,
            "Engineer",
            "Engineering",
            "alice@company.com",
            "+44123",
            "+44456",
            "Ali",
            "alice@personal.com",
            "Strong candidate",
            "Good performer",
            "75000",
            "75000",
            "Full-Time",
            "Active",
            "Senior",
            "IC",
            "2020-01-15",
            "",
            "",
            "Hired",
            "75000",
            "",
            "London",
            "UK",
            "true",
            "London",
            "UK",
            "Europe",
        ),
        (
            "EMP002",
            "Bob Jones",
            "Bob",
            "Jones",
            _EMPLOYEE_RT_ID,
            "Manager",
            "Engineering",
            "bob@company.com",
            "+44789",
            "+44012",
            "Bobby",
            "bob@personal.com",
            "",
            "Leadership track",
            "95000",
            "95000",
            "Full-Time",
            "Active",
            "Lead",
            "Manager",
            "2018-06-01",
            "",
            "",
            "Hired",
            "95000",
            "10000",
            "Bristol",
            "UK",
            "true",
            "Bristol",
            "UK",
            "Europe",
        ),
        (
            "EMP003",
            "Carol White",
            "Carol",
            "White",
            _EMPLOYEE_RT_ID,
            "Analyst",
            "Finance",
            "carol@company.com",
            "",
            "",
            "",
            "carol@personal.com",
            "Referred by Bob",
            "",
            "55000",
            "55000",
            "Full-Time",
            "Active",
            "Mid",
            "IC",
            "2022-03-10",
            "",
            "",
            "Hired",
            "55000",
            "",
            "London",
            "UK",
            "true",
            "London",
            "UK",
            "Europe",
        ),
    ]
    for emp in employees:
        cur.execute(
            "INSERT INTO contact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            emp,
        )

    # Insert contractors
    contractors = [
        (
            "CON001",
            "Dave Brown",
            "Dave",
            "Brown",
            _CONTRACTOR_RT_ID,
            "Consultant",
            "Engineering",
            "dave@contractor.com",
            "+44111",
            "",
            "Dave",
            "dave@personal.com",
            "Agency referral",
            "Good contractor",
            "800",
            "800",
            "Contractor",
            "Active",
            "",
            "Consultant",
            "2023-01-01",
            "2024-12-31",
            "2024-06-01",
            "",
            "800",
            "",
            "Remote",
            "India",
            "true",
            "Mumbai",
            "India",
            "India",
        ),
        (
            "CON002",
            "Eve Green",
            "Eve",
            "Green",
            _CONTRACTOR_RT_ID,
            "Designer",
            "Design",
            "eve@contractor.com",
            "",
            "",
            "Evie",
            "eve@personal.com",
            "",
            "",
            "600",
            "600",
            "Contractor",
            "Active",
            "",
            "Designer",
            "2023-06-15",
            "2025-06-15",
            "2025-01-01",
            "",
            "600",
            "",
            "London",
            "UK",
            "true",
            "London",
            "UK",
            "Europe",
        ),
    ]
    for con in contractors:
        cur.execute(
            "INSERT INTO contact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            con,
        )

    # Insert a customer contact (should not appear in HR viewer)
    cur.execute(
        "INSERT INTO contact VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "CUST001",
            "Frank Customer",
            "Frank",
            "Customer",
            "012200000002Ns8AAE",
            "Buyer",
            "Procurement",
            "frank@customer.com",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
    )

    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def hr_db_with_record_type(hr_db: Path) -> Path:
    """Extend hr_db with a record_type table."""
    conn = sqlite3.connect(str(hr_db))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE record_type (
            Id TEXT PRIMARY KEY,
            Name TEXT,
            DeveloperName TEXT,
            SobjectType TEXT
        )
    """)
    cur.execute(
        "INSERT INTO record_type VALUES (?, ?, ?, ?)",
        (_EMPLOYEE_RT_ID, "Employee", "Employee", "Contact"),
    )
    cur.execute(
        "INSERT INTO record_type VALUES (?, ?, ?, ?)",
        (_CONTRACTOR_RT_ID, "Contractor", "Contractor", "Contact"),
    )
    cur.execute(
        "INSERT INTO record_type VALUES (?, ?, ?, ?)",
        ("012200000002Ns8AAE", "Customer", "Customer", "Contact"),
    )
    conn.commit()
    conn.close()
    return hr_db


# ---------------------------------------------------------------------------
# Field definition tests
# ---------------------------------------------------------------------------


class TestFieldDefinitions:
    """Verify that field tuples are well-formed."""

    def test_common_fields_has_name(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Name" in col_names

    def test_common_fields_has_known_as(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Known_As__c" in col_names

    def test_common_fields_has_title(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Title" in col_names

    def test_common_fields_has_personal_email(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Personal_Email_Address__c" in col_names

    def test_common_fields_has_hiring_comments(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Comments_Hiring__c" in col_names

    def test_common_fields_has_hr_comments(self):
        col_names = [col for col, _ in _COMMON_FIELDS]
        assert "Son_Comments_HR__c" in col_names

    def test_contractor_extra_has_salary(self):
        col_names = [col for col, _ in _CONTRACTOR_EXTRA_FIELDS]
        assert "Son_Salary__c" in col_names

    def test_employee_extra_has_grade(self):
        col_names = [col for col, _ in _EMPLOYEE_EXTRA_FIELDS]
        assert "Grade__c" in col_names

    def test_detail_fields_has_all_key_fields(self):
        col_names = [col for col, _ in _DETAIL_FIELDS]
        assert "Id" in col_names
        assert "Name" in col_names
        assert "Son_Salary__c" in col_names
        assert "Comments_Hiring__c" in col_names
        assert "Son_Comments_HR__c" in col_names

    def test_filter_fields_has_region(self):
        col_names = [col for col, _ in _FILTER_FIELDS]
        assert "Region__c" in col_names
        assert "Location__c" in col_names

    def test_filter_fields_has_name_parts(self):
        col_names = [col for col, _ in _FILTER_FIELDS]
        assert "FirstName" in col_names
        assert "LastName" in col_names

    def test_detail_fields_has_region(self):
        col_names = [col for col, _ in _DETAIL_FIELDS]
        assert "Region__c" in col_names

    def test_all_field_tuples_are_pairs(self):
        """Every field definition should be (column_name, label) pair."""
        for fields in [
            _COMMON_FIELDS,
            _CONTRACTOR_EXTRA_FIELDS,
            _EMPLOYEE_EXTRA_FIELDS,
            _FILTER_FIELDS,
            _DETAIL_FIELDS,
        ]:
            for item in fields:
                assert len(item) == 2, f"Expected (col, label) pair, got {item}"
                assert isinstance(item[0], str)
                assert isinstance(item[1], str)


# ---------------------------------------------------------------------------
# RecordType ID constants
# ---------------------------------------------------------------------------


class TestRecordTypeConstants:
    def test_employee_rt_id_format(self):
        assert _EMPLOYEE_RT_ID.startswith("012")
        assert len(_EMPLOYEE_RT_ID) == 18

    def test_contractor_rt_id_format(self):
        assert _CONTRACTOR_RT_ID.startswith("012")
        assert len(_CONTRACTOR_RT_ID) == 18

    def test_employee_and_contractor_ids_differ(self):
        assert _EMPLOYEE_RT_ID != _CONTRACTOR_RT_ID


# ---------------------------------------------------------------------------
# Database helper tests
# ---------------------------------------------------------------------------


class TestGetAvailableColumns:
    def test_returns_contact_columns(self, hr_db: Path):
        conn = sqlite3.connect(str(hr_db))
        cur = conn.cursor()
        cols = _get_available_columns(cur)
        conn.close()

        assert "Id" in cols
        assert "Name" in cols
        assert "RecordTypeId" in cols
        assert "Known_As__c" in cols
        assert "Son_Salary__c" in cols

    def test_returns_set_type(self, hr_db: Path):
        conn = sqlite3.connect(str(hr_db))
        cur = conn.cursor()
        cols = _get_available_columns(cur)
        conn.close()

        assert isinstance(cols, set)


class TestHasRecordTypeTable:
    def test_no_record_type_table(self, hr_db: Path):
        conn = sqlite3.connect(str(hr_db))
        cur = conn.cursor()
        assert _has_record_type_table(cur) is False
        conn.close()

    def test_with_record_type_table(self, hr_db_with_record_type: Path):
        conn = sqlite3.connect(str(hr_db_with_record_type))
        cur = conn.cursor()
        assert _has_record_type_table(cur) is True
        conn.close()


# ---------------------------------------------------------------------------
# Count by type
# ---------------------------------------------------------------------------


class TestCountByType:
    def test_counts_employees_and_contractors(self, hr_db: Path):
        counts = _count_by_type(hr_db)
        assert counts["Employee"] == 3
        assert counts["Contractor"] == 2

    def test_excludes_customer_contacts(self, hr_db: Path):
        counts = _count_by_type(hr_db)
        # Customer contact should not appear in either count
        total = counts.get("Employee", 0) + counts.get("Contractor", 0)
        assert total == 5  # 3 employees + 2 contractors, not 6


# ---------------------------------------------------------------------------
# Load contacts
# ---------------------------------------------------------------------------


class TestLoadContacts:
    def test_load_employees(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields)

        assert len(df) == 3
        assert "Name" in df.columns
        assert "Known As" in df.columns
        assert "Title" in df.columns

    def test_load_contractors(self, hr_db: Path):
        fields = _COMMON_FIELDS + _CONTRACTOR_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _CONTRACTOR_RT_ID, fields)

        assert len(df) == 2
        assert "Salary" in df.columns  # Contractor-specific field

    def test_search_filters_by_first_name(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="alice")

        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_search_filters_by_last_name(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="jones")

        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Bob Jones"

    def test_search_does_not_match_title(self, hr_db: Path):
        """Search is name-only; titles should not match."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="manager")

        assert len(df) == 0

    def test_search_case_insensitive(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="ALICE")

        assert len(df) == 1

    def test_search_no_match_returns_empty(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="nonexistent")

        assert len(df) == 0

    def test_empty_search_returns_all(self, hr_db: Path):
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="")

        assert len(df) == 3

    def test_includes_id_column(self, hr_db: Path):
        """Id column is always included for drill-down."""
        fields = _COMMON_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields)

        assert "Id" in df.columns

    def test_with_record_type_table(self, hr_db_with_record_type: Path):
        """Works with record_type table JOIN approach."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db_with_record_type, _EMPLOYEE_RT_ID, fields)

        assert len(df) == 3

    def test_handles_missing_column_gracefully(self, tmp_path: Path):
        """If a requested field doesn't exist in the table, it's skipped."""
        db_path = tmp_path / "minimal.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE contact (Id TEXT PRIMARY KEY, Name TEXT, RecordTypeId TEXT)")
        conn.execute(
            "INSERT INTO contact VALUES (?, ?, ?)",
            ("001", "Test", _EMPLOYEE_RT_ID),
        )
        conn.commit()
        conn.close()

        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS
        df = _load_contacts(db_path, _EMPLOYEE_RT_ID, fields)

        assert len(df) == 1
        assert "Name" in df.columns
        # Missing fields should not cause errors
        assert "Known As" not in df.columns  # Known_As__c doesn't exist in minimal DB


# ---------------------------------------------------------------------------
# Load contact detail
# ---------------------------------------------------------------------------


class TestLoadContactDetail:
    def test_loads_employee_detail(self, hr_db: Path):
        detail = _load_contact_detail(hr_db, "EMP001")

        assert detail["Name"] == "Alice Smith"
        assert detail["Known As"] == "Ali"
        assert detail["Title"] == "Engineer"
        assert detail["Personal Email"] == "alice@personal.com"
        assert detail["Hiring Comments"] == "Strong candidate"
        assert detail["HR Comments"] == "Good performer"

    def test_loads_contractor_detail(self, hr_db: Path):
        detail = _load_contact_detail(hr_db, "CON001")

        assert detail["Name"] == "Dave Brown"
        assert detail["Salary"] == "800"
        assert detail["Contract Renewal"] == "2024-06-01"

    def test_nonexistent_contact_returns_empty(self, hr_db: Path):
        detail = _load_contact_detail(hr_db, "DOESNOTEXIST")

        assert detail == {}

    def test_empty_values_become_empty_string(self, hr_db: Path):
        detail = _load_contact_detail(hr_db, "EMP003")

        # Carol has empty Known_As__c
        assert detail["Known As"] == ""

    def test_returns_dict_type(self, hr_db: Path):
        detail = _load_contact_detail(hr_db, "EMP001")

        assert isinstance(detail, dict)
        for key, value in detail.items():
            assert isinstance(key, str)
            assert isinstance(value, str)


# ---------------------------------------------------------------------------
# Wildcard search
# ---------------------------------------------------------------------------


class TestWildcardSearch:
    def test_star_wildcard_first_name(self, hr_db: Path):
        """Star wildcard matches first name prefix."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Ali*")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_first_name_star_matches_any_surname(self, hr_db: Path):
        """'Alice *' matches FirstName=Alice with any surname."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Alice *")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_first_name_partial_surname(self, hr_db: Path):
        """'Alice Sm*' matches FirstName=Alice, Surname starting Sm."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Alice Sm*")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_first_name_star_excludes_wrong_first(self, hr_db: Path):
        """'Alice *' should NOT match Bob Jones."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Alice *")
        names = df["Name"].tolist()
        assert "Bob Jones" not in names

    def test_question_mark_wildcard(self, hr_db: Path):
        """Question mark matches single character."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="?ob *")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Bob Jones"

    def test_reversed_name_order(self, hr_db: Path):
        """Searching surname-first matches via reversed variant."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Smith *")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_known_as_search(self, hr_db: Path):
        """Searching by known-as name finds the contact."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Bobby *")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Bob Jones"

    def test_known_as_reversed(self, hr_db: Path):
        """Searching surname + known-as finds the contact."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="Jones Bobby")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Bob Jones"

    def test_star_contains_name(self, hr_db: Path):
        """Star on both sides matches name substring."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="*mith*")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_does_not_match_non_name_fields(self, hr_db: Path):
        """Search should not match against email, title, comments, etc."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        # "Engineer" is Alice's title, not a name
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="*engineer*")
        assert len(df) == 0

    def test_wildcard_case_insensitive(self, hr_db: Path):
        """Wildcard search is case-insensitive."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="ALICE*")
        assert len(df) == 1

    def test_wildcard_no_match(self, hr_db: Path):
        """Wildcard with no match returns empty."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="xyz*zzz")
        assert len(df) == 0

    def test_plain_search_auto_wraps(self, hr_db: Path):
        """Plain text without wildcards auto-wraps in *...* for contains."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="alice")
        assert len(df) == 1


# ---------------------------------------------------------------------------
# Name variants
# ---------------------------------------------------------------------------


class TestNameVariants:
    def test_first_last(self):
        """Generates FirstName LastName variant."""
        row = pd.Series({"First Name": "Alice", "Last Name": "Smith", "Known As": ""})
        variants = _name_variants(row)
        assert "Alice Smith" in variants

    def test_reversed(self):
        """Generates LastName FirstName variant."""
        row = pd.Series({"First Name": "Alice", "Last Name": "Smith", "Known As": ""})
        variants = _name_variants(row)
        assert "Smith Alice" in variants

    def test_known_as_variant(self):
        """Generates KnownAs LastName variant when different from FirstName."""
        row = pd.Series({"First Name": "Robert", "Last Name": "Jones", "Known As": "Bobby"})
        variants = _name_variants(row)
        assert "Bobby Jones" in variants
        assert "Jones Bobby" in variants

    def test_known_as_same_as_first_skipped(self):
        """Skips KnownAs variant when it matches FirstName."""
        row = pd.Series({"First Name": "Dave", "Last Name": "Brown", "Known As": "Dave"})
        variants = _name_variants(row)
        # Should have FirstLast and LastFirst, but no duplicate known-as variants
        assert variants == ["Dave Brown", "Brown Dave"]

    def test_no_known_as(self):
        """Works when KnownAs is empty."""
        row = pd.Series({"First Name": "Carol", "Last Name": "White", "Known As": ""})
        variants = _name_variants(row)
        assert "Carol White" in variants
        assert "White Carol" in variants
        assert len(variants) == 2

    def test_first_only(self):
        """Handles contact with only first name."""
        row = pd.Series({"First Name": "Alice", "Last Name": "", "Known As": ""})
        variants = _name_variants(row)
        assert variants == ["Alice"]

    def test_last_only(self):
        """Handles contact with only last name."""
        row = pd.Series({"First Name": "", "Last Name": "Smith", "Known As": ""})
        variants = _name_variants(row)
        assert variants == ["Smith"]

    def test_known_as_case_insensitive_dedup(self):
        """KnownAs 'bob' is treated as same as FirstName 'Bob'."""
        row = pd.Series({"First Name": "Bob", "Last Name": "Jones", "Known As": "bob"})
        variants = _name_variants(row)
        assert variants == ["Bob Jones", "Jones Bob"]


# ---------------------------------------------------------------------------
# Region filter
# ---------------------------------------------------------------------------


class TestRegionFilter:
    def test_filter_by_europe(self, hr_db: Path):
        """Filtering by Europe returns European employees."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, region="Europe")
        assert len(df) == 3  # All employees are in Europe

    def test_filter_by_india(self, hr_db: Path):
        """Filtering by India returns Indian contractors."""
        fields = _COMMON_FIELDS + _CONTRACTOR_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _CONTRACTOR_RT_ID, fields, region="India")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Dave Brown"

    def test_filter_by_nonexistent_region(self, hr_db: Path):
        """Filtering by non-existent region returns empty."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, region="Mars")
        assert len(df) == 0

    def test_filter_region_case_insensitive(self, hr_db: Path):
        """Region filter is case-insensitive."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, region="europe")
        assert len(df) == 3

    def test_region_and_search_combined(self, hr_db: Path):
        """Region filter and search work together."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, search="alice", region="Europe")
        assert len(df) == 1
        assert df.iloc[0]["Name"] == "Alice Smith"

    def test_empty_region_returns_all(self, hr_db: Path):
        """Empty region string returns all contacts."""
        fields = _COMMON_FIELDS + _EMPLOYEE_EXTRA_FIELDS + _FILTER_FIELDS
        df = _load_contacts(hr_db, _EMPLOYEE_RT_ID, fields, region="")
        assert len(df) == 3


# ---------------------------------------------------------------------------
# Load regions
# ---------------------------------------------------------------------------


class TestLoadRegions:
    def test_returns_sorted_regions(self, hr_db: Path):
        regions = _load_regions(hr_db)
        assert isinstance(regions, list)
        assert "Europe" in regions
        assert "India" in regions
        assert regions == sorted(regions)

    def test_excludes_empty_regions(self, hr_db: Path):
        regions = _load_regions(hr_db)
        assert "" not in regions

    def test_excludes_customer_regions(self, hr_db: Path):
        """Regions from non-employee/contractor contacts are excluded."""
        regions = _load_regions(hr_db)
        # Customer has empty region, so this just checks no unexpected values
        for r in regions:
            assert r in ("Europe", "India")

    def test_no_region_column(self, tmp_path: Path):
        """Returns empty list if Region__c column doesn't exist."""
        db_path = tmp_path / "minimal.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE contact (Id TEXT PRIMARY KEY, Name TEXT, RecordTypeId TEXT)")
        conn.commit()
        conn.close()

        regions = _load_regions(db_path)
        assert regions == []


# ---------------------------------------------------------------------------
# Schema integration: RecordType in OBJECTS registry
# ---------------------------------------------------------------------------


class TestSchemaIntegration:
    def test_record_type_in_objects(self):
        from sfdump.indexing import OBJECTS

        assert "RecordType" in OBJECTS

    def test_record_type_table_name(self):
        from sfdump.indexing import OBJECTS

        rt = OBJECTS["RecordType"]
        assert rt.table_name == "record_type"
        assert rt.api_name == "RecordType"
        assert rt.label == "Record Type"

    def test_contact_still_in_objects(self):
        from sfdump.indexing import OBJECTS

        assert "Contact" in OBJECTS
        assert OBJECTS["Contact"].table_name == "contact"


# ---------------------------------------------------------------------------
# DB builder: RecordType table gets created
# ---------------------------------------------------------------------------


class TestDbBuilderRecordType:
    def test_record_type_table_created(self, tmp_path: Path):
        """RecordType CSV produces a record_type table in SQLite."""
        from sfdump.viewer import build_sqlite_from_export

        export_dir = tmp_path / "export"
        export_dir.mkdir()
        csv_dir = export_dir / "csv"
        csv_dir.mkdir()

        # Minimal RecordType.csv
        (csv_dir / "RecordType.csv").write_text(
            "Id,Name,DeveloperName,SobjectType\n"
            f"{_EMPLOYEE_RT_ID},Employee,Employee,Contact\n"
            f"{_CONTRACTOR_RT_ID},Contractor,Contractor,Contact\n",
            encoding="utf-8",
        )

        # Minimal Contact.csv
        (csv_dir / "Contact.csv").write_text(
            f"Id,Name,RecordTypeId\n001,Alice,{_EMPLOYEE_RT_ID}\n002,Dave,{_CONTRACTOR_RT_ID}\n",
            encoding="utf-8",
        )

        db_path = tmp_path / "sfdata.db"
        build_sqlite_from_export(export_dir, db_path)

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Verify record_type table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='record_type'")
        assert cur.fetchone() is not None

        # Verify data
        cur.execute("SELECT COUNT(*) FROM record_type")
        assert cur.fetchone()[0] == 2

        cur.execute("SELECT Name FROM record_type WHERE Id = ?", [_EMPLOYEE_RT_ID])
        assert cur.fetchone()[0] == "Employee"

        conn.close()
