"""HR Viewer — Contact records split by Employee / Contractor.

Queries the SQLite database to show Contact records grouped by RecordType
(Employee vs Contractor), displaying key HR fields in a searchable table
with drill-down to individual record detail.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from sfdump.utils import glob_to_regex

# RecordType IDs for Employee and Contractor (from RecordType.csv)
_EMPLOYEE_RT_ID = "012200000002Ns3AAE"
_CONTRACTOR_RT_ID = "012200000002NryAAE"

# Fields to display for each group
_COMMON_FIELDS = [
    ("Name", "Name"),
    ("Known_As__c", "Known As"),
    ("Title", "Title"),
    ("Personal_Email_Address__c", "Personal Email"),
    ("Email", "Work Email"),
    ("Department", "Department"),
    ("Comments_Hiring__c", "Hiring Comments"),
    ("Son_Comments_HR__c", "HR Comments"),
]

_CONTRACTOR_EXTRA_FIELDS = [
    ("Son_Salary__c", "Salary"),
    ("Current_salary__c", "Current Salary"),
    ("ContractRenewalDate__c", "Contract Renewal Date"),
]

_EMPLOYEE_EXTRA_FIELDS = [
    ("Grade__c", "Grade"),
    ("Son_Employment_Type__c", "Employment Type"),
    ("Employment_Status__c", "Employment Status"),
    ("Confirmed_Start_Date__c", "Start Date"),
]

# Extra columns loaded for filtering/search (not displayed in table)
_FILTER_FIELDS = [
    ("FirstName", "First Name"),
    ("LastName", "Last Name"),
    ("Location__c", "Location"),
    ("Region__c", "Region"),
]

_DETAIL_FIELDS = [
    ("Id", "ID"),
    ("Name", "Name"),
    ("FirstName", "First Name"),
    ("LastName", "Last Name"),
    ("Known_As__c", "Known As"),
    ("Title", "Title"),
    ("Department", "Department"),
    ("Email", "Work Email"),
    ("Personal_Email_Address__c", "Personal Email"),
    ("Phone", "Phone"),
    ("MobilePhone", "Mobile"),
    ("Son_Employment_Type__c", "Employment Type"),
    ("Employment_Status__c", "Employment Status"),
    ("Grade__c", "Grade"),
    ("Resource_Role__c", "Resource Role"),
    ("Confirmed_Start_Date__c", "Start Date"),
    ("Effective_End_Date__c", "End Date"),
    ("ContractRenewalDate__c", "Contract Renewal"),
    ("Son_Salary__c", "Salary"),
    ("Current_salary__c", "Current Salary"),
    ("Fixed_compensation_Local__c", "Fixed Compensation"),
    ("Variable_compensation_OTE__c", "Variable Comp (OTE)"),
    ("Comments_Hiring__c", "Hiring Comments"),
    ("Son_Comments_HR__c", "HR Comments"),
    ("Son_Hiring_Status__c", "Hiring Status"),
    ("Location__c", "Location"),
    ("Region__c", "Region"),
    ("Nationality__c", "Nationality"),
    ("Active__c", "Active"),
    ("MailingCity", "City"),
    ("MailingCountry", "Country"),
]


def _name_variants(row: pd.Series) -> list[str]:
    """Build name variant strings for search matching.

    Generates variants in these orders:
    1. FirstName LastName
    2. KnownAs LastName (if KnownAs differs from FirstName)
    3. LastName FirstName
    4. LastName KnownAs (if KnownAs differs from FirstName)
    """
    first = str(row.get("First Name") or "").strip()
    last = str(row.get("Last Name") or "").strip()
    known = str(row.get("Known As") or "").strip()

    has_distinct_known = known and known.lower() != first.lower()
    variants: list[str] = []

    # Forward: first last
    if first and last:
        variants.append(f"{first} {last}")
    elif first:
        variants.append(first)
    elif last:
        variants.append(last)

    # Forward with known-as
    if has_distinct_known:
        if last:
            variants.append(f"{known} {last}")
        else:
            variants.append(known)

    # Reversed: last first
    if first and last:
        variants.append(f"{last} {first}")

    # Reversed with known-as
    if has_distinct_known and last:
        variants.append(f"{last} {known}")

    return variants


def _get_available_columns(cursor: sqlite3.Cursor) -> set[str]:
    """Return the set of column names in the contact table."""
    cursor.execute("PRAGMA table_info(contact)")
    return {row[1] for row in cursor.fetchall()}


def _has_record_type_table(cursor: sqlite3.Cursor) -> bool:
    """Check if the record_type table exists in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='record_type'")
    return cursor.fetchone() is not None


def _load_contacts(
    db_path: Path,
    record_type_id: str,
    fields: list[tuple[str, str]],
    search: str = "",
    region: str = "",
) -> pd.DataFrame:
    """Load contacts of a given RecordType, selecting only available fields."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        available = _get_available_columns(cur)

        # Always include Id for detail drill-down
        select_cols = ["Id"]
        col_labels = ["Id"]
        for col, label in fields:
            if col in available and col not in select_cols:
                select_cols.append(col)
                col_labels.append(label)

        # Determine how to filter: use record_type table if available,
        # otherwise use hardcoded RecordTypeId
        if _has_record_type_table(cur):
            # Join approach — qualify columns with table alias to avoid ambiguity
            cols_sql = ", ".join(f'c."{c}"' for c in select_cols)
            query = (
                f"SELECT {cols_sql} FROM contact c "
                f"JOIN record_type rt ON c.RecordTypeId = rt.Id "
                f"WHERE rt.Id = ?"
            )
            params: list = [record_type_id]
        else:
            cols_sql = ", ".join(f'"{c}"' for c in select_cols)
            # Direct ID comparison — works with existing databases
            if "RecordTypeId" in available:
                query = f"SELECT {cols_sql} FROM contact WHERE RecordTypeId = ?"
                params = [record_type_id]
            else:
                # No way to filter — show all contacts
                query = f"SELECT {cols_sql} FROM contact"
                params = []

        cur.execute(query, params)
        rows = cur.fetchall()
    finally:
        conn.close()

    df = pd.DataFrame(rows, columns=col_labels)

    # Region filter (exact match)
    if region and "Region" in df.columns:
        df = df[df["Region"].astype(str).str.lower() == region.lower()]

    # Name-only search (glob pattern matched against name variants)
    if search:
        raw = search.lower()
        # Auto-wrap plain text (no glob chars) in wildcards for "contains" behaviour
        if not any(c in raw for c in "*?["):
            raw = f"*{raw}*"
        regex = re.compile(glob_to_regex(raw))

        def _matches(row: pd.Series) -> bool:
            return any(regex.fullmatch(v.lower()) for v in _name_variants(row))

        df = df[df.apply(_matches, axis=1)]

    return df


def _load_contact_detail(db_path: Path, contact_id: str) -> dict[str, str]:
    """Load all fields for a single contact record."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        available = _get_available_columns(cur)

        select_cols = []
        col_labels = []
        for col, label in _DETAIL_FIELDS:
            if col in available:
                select_cols.append(col)
                col_labels.append(label)

        cols_sql = ", ".join(f'"{c}"' for c in select_cols)
        cur.execute(f"SELECT {cols_sql} FROM contact WHERE Id = ?", [contact_id])
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return {}

    return {label: (val if val else "") for label, val in zip(col_labels, row, strict=False)}


def _count_by_type(db_path: Path) -> dict[str, int]:
    """Return counts of Employee and Contractor contacts."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        available = _get_available_columns(cur)
        if "RecordTypeId" not in available:
            return {"Employee": 0, "Contractor": 0}

        cur.execute(
            "SELECT RecordTypeId, COUNT(*) FROM contact "
            "WHERE RecordTypeId IN (?, ?) GROUP BY RecordTypeId",
            [_EMPLOYEE_RT_ID, _CONTRACTOR_RT_ID],
        )
        result = {}
        for rt_id, count in cur.fetchall():
            if rt_id == _EMPLOYEE_RT_ID:
                result["Employee"] = count
            elif rt_id == _CONTRACTOR_RT_ID:
                result["Contractor"] = count
    finally:
        conn.close()

    return result


def _load_regions(db_path: Path) -> list[str]:
    """Return sorted list of distinct Region__c values."""
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        available = _get_available_columns(cur)
        if "Region__c" not in available:
            return []
        cur.execute(
            "SELECT DISTINCT Region__c FROM contact "
            "WHERE Region__c IS NOT NULL AND Region__c != '' "
            "AND RecordTypeId IN (?, ?) "
            "ORDER BY Region__c",
            [_EMPLOYEE_RT_ID, _CONTRACTOR_RT_ID],
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def render_hr_viewer(*, db_path: Path) -> None:
    """Main HR viewer entry point."""
    # Check contact table exists
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='contact'")
        if cur.fetchone() is None:
            st.error(
                "No `contact` table found in the database. "
                "Ensure your export includes Contact records and rebuild the DB."
            )
            return
    finally:
        conn.close()

    # Counts
    counts = _count_by_type(db_path)
    emp_count = counts.get("Employee", 0)
    con_count = counts.get("Contractor", 0)

    # Detail view state
    detail_key = "_hr_detail_contact_id"
    detail_id = st.session_state.get(detail_key)

    if detail_id:
        _render_contact_detail(db_path, detail_id, detail_key)
        return

    st.subheader("Contact Search")
    st.caption("Search across Employees and Contractors")

    # Search box
    q = st.text_input(
        "Search",
        value="",
        key="hr_search",
        placeholder="e.g. Kevin *, *Smith, Ali*, Smith Kev*...",
        help="Search by name (first, last, or known-as). Supports wildcards.",
    ).strip()

    # Search tips (collapsed by default)
    with st.expander("Search tips"):
        st.markdown(
            """
| Pattern | Meaning | Example |
|---------|---------|---------|
| `Kevin *` | First name + any surname | Matches Kevin Smith, Kevin Jones, ... |
| `*smith` | Surname ends with | Matches any name ending in "smith" |
| `Ali*` | Starts with | Matches Alice Smith, Alison Green, ... |
| `Smith *` | Surname first | Finds via reversed name order |
| `?ob *` | Single char wildcard | Matches Bob, Rob + any surname |
| `[A-M]*` | Range | Names starting A to M |
| `kevin` | Plain text (no wildcards) | Auto-wraps as `*kevin*` — contains match |

Search matches against first name, last name, and "known as" name.
Names are matched in both orders (e.g. "Kevin Smith" and "Smith Kevin").
"""
        )

    # Region filter and match count on same row
    col_region, col_count = st.columns([1, 3])
    with col_region:
        regions = _load_regions(db_path)
        region = ""
        if regions:
            region_options = ["All Regions"] + regions
            selected_region = st.selectbox(
                "Region",
                options=region_options,
                index=0,
                key="hr_region",
            )
            if selected_region != "All Regions":
                region = selected_region

    has_filter = bool(q or region)

    with col_count:
        if has_filter:
            st.markdown("")  # spacing
        else:
            st.markdown(
                f"**{emp_count + con_count:,}** contacts available "
                f"({emp_count:,} employees, {con_count:,} contractors)"
            )

    if not has_filter:
        return

    # Tabs for Employee / Contractor
    tab_emp, tab_con = st.tabs(
        [
            f"Employees ({emp_count})",
            f"Contractors ({con_count})",
        ]
    )

    with tab_emp:
        _render_contact_table(
            db_path=db_path,
            record_type_id=_EMPLOYEE_RT_ID,
            extra_fields=_EMPLOYEE_EXTRA_FIELDS,
            search=q,
            region=region,
            key_prefix="emp",
            detail_key=detail_key,
        )

    with tab_con:
        _render_contact_table(
            db_path=db_path,
            record_type_id=_CONTRACTOR_RT_ID,
            extra_fields=_CONTRACTOR_EXTRA_FIELDS,
            search=q,
            region=region,
            key_prefix="con",
            detail_key=detail_key,
        )


def _render_contact_table(
    *,
    db_path: Path,
    record_type_id: str,
    extra_fields: list[tuple[str, str]],
    search: str,
    region: str,
    key_prefix: str,
    detail_key: str,
) -> None:
    """Render a table of contacts for a given record type."""
    fields = _COMMON_FIELDS + extra_fields + _FILTER_FIELDS

    df = _load_contacts(db_path, record_type_id, fields, search, region)

    if df.empty:
        st.info("No contacts found. Try a different search or region.")
        return

    st.markdown(f"**{len(df)}** record(s) found")

    # Display columns (exclude Id and filter-only columns from display)
    hide_cols = {"Id", "First Name", "Last Name", "Location", "Region"}
    display_cols = [c for c in df.columns if c not in hide_cols]

    st.dataframe(
        df[display_cols],
        hide_index=True,
        height=min(400, 35 * len(df) + 38),
        width="stretch",
        column_config={
            "Name": st.column_config.TextColumn("Name", width="large"),
        },
    )

    # Record selector for detail view
    options = df.apply(
        lambda r: f"{r.get('Name', '')} — {r.get('Title', '') or ''}".strip(" —"),
        axis=1,
    ).tolist()
    ids = df["Id"].tolist()

    selected_idx = st.selectbox(
        "Select a contact to view details",
        range(len(options)),
        format_func=lambda i: options[i],
        key=f"{key_prefix}_select",
    )

    if st.button("View Details", key=f"{key_prefix}_detail_btn"):
        st.session_state[detail_key] = ids[selected_idx]
        st.rerun()


def _render_contact_detail(db_path: Path, contact_id: str, detail_key: str) -> None:
    """Render detailed view of a single contact."""
    if st.button("Back to list", key="hr_back_btn"):
        del st.session_state[detail_key]
        st.rerun()

    data = _load_contact_detail(db_path, contact_id)

    if not data:
        st.error(f"Contact {contact_id} not found.")
        return

    name = data.get("Name", contact_id)
    st.subheader(name)

    # Split into two columns for readability
    col1, col2 = st.columns(2)

    items = list(data.items())
    mid = (len(items) + 1) // 2

    with col1:
        detail_df = pd.DataFrame(
            [{"Field": k, "Value": v} for k, v in items[:mid] if v],
        )
        if not detail_df.empty:
            st.table(detail_df)

    with col2:
        detail_df = pd.DataFrame(
            [{"Field": k, "Value": v} for k, v in items[mid:] if v],
        )
        if not detail_df.empty:
            st.table(detail_df)
