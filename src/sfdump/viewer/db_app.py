from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import streamlit as st

from sfdump.indexing import OBJECTS
from sfdump.viewer import get_record_with_children, inspect_sqlite_db, list_records

IMPORTANT_FIELDS = {
    "Account": ["Id", "Name", "AccountNumber", "Type", "Industry"],
    "Opportunity": ["Id", "Name", "StageName", "CloseDate", "Amount"],
    "Contact": ["Id", "Name", "Email", "Phone", "Title"],
    "ContentDocument": ["Id", "Title", "LatestPublishedVersionId"],
    "ContentVersion": ["Id", "Title", "VersionNumber", "CreatedDate"],
    "ContentDocumentLink": ["Id", "LinkedEntityId", "ContentDocumentId", "ShareType", "Visibility"],
    "Attachment": ["Id", "ParentId", "Name", "ContentType", "BodyLength"],
    # 🧾 Finance objects – adjust field names once you see the actual CSV headers
    "Invoice": [
        "Id",
        "Name",  # if present
        "InvoiceNumber",  # common pattern
        "InvoiceDate",
        "Status",  # or "Status__c"
        "TotalAmount",  # or "Total__c" / "Amount__c"
        "Balance",  # or "Balance__c"
    ],
    "InvoiceLine": [
        "Id",
        "InvoiceId",
        "LineNumber",  # often exists
        "ProductName",  # or "Name" / "Product__c"
        "Description",
        "Quantity",
        "UnitPrice",
        "Amount",  # or "Amount__c"
    ],
    "CreditNote": [
        "Id",
        "Name",
        "CreditNoteNumber",  # or "Credit_Number__c"
        "CreditNoteDate",
        "Status",
        "TotalAmount",
        "Balance",
    ],
    "CreditNoteLine": [
        "Id",
        "CreditNoteId",
        "LineNumber",
        "Description",
        "Quantity",
        "UnitPrice",
        "Amount",
    ],
    "c2g__codaInvoiceLineItem__c": [
        "Id",
        "Name",
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__Quantity__c",
        "c2g__UnitPrice__c",
        "c2g__NetValue__c",
        "c2g__TaxRateTotal__c",
        "c2g__TaxValueTotal__c",
        "c2g__ProductCode__c",
        "c2g__ProductReference__c",
    ],
    "OpportunityLineItem": [
        "Id",
        "OpportunityId",
        "PricebookEntryId",
        "Product2Id",  # often present
        "Quantity",
        "UnitPrice",
        "TotalPrice",
        "Description",
    ],
}


def _get_important_fields(api_name: str) -> list[str]:
    """Return the configured 'important' fields for this object, if any."""
    return IMPORTANT_FIELDS.get(api_name, [])


def _select_display_columns(api_name: str, df, show_all: bool) -> list[str]:
    """
    Decide which columns to show for a given object + DataFrame.

    - If show_all: return all columns.
    - Else: use IMPORTANT_FIELDS if present.
    - Else: fall back to a simple Id/Name/... heuristic.
    """
    cols = list(df.columns)

    if show_all:
        return cols

    # 1) Try configured IMPORTANT_FIELDS
    important = _get_important_fields(api_name)
    display_cols: list[str] = [c for c in important if c in cols]

    # 2) If no configured fields (or none matched), use generic heuristic
    if not display_cols:
        for col in ("Id", "Name"):
            if col in cols and col not in display_cols:
                display_cols.append(col)

        for extra in ("Email", "Title", "StageName", "Amount"):
            if extra in cols and extra not in display_cols:
                display_cols.append(extra)

    # 3) Fallback: if still empty, just take the first few columns
    if not display_cols:
        display_cols = cols[:5]

    return display_cols


def _initial_db_path_from_argv() -> Optional[Path]:
    # When launched via: streamlit run db_viewer_app.py -- <db-path>
    # sys.argv for this script will look like: ['db_viewer_app.py', '<db-path>']
    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)
    return None


def _get_object_choices(tables) -> list[str]:
    """Return a sorted list of API names for objects that actually exist in the DB."""
    table_names = {t.name for t in tables}
    api_names: list[str] = []
    for obj in OBJECTS.values():
        if obj.table_name in table_names:
            api_names.append(obj.api_name)
    return sorted(api_names)


def main() -> None:
    st.set_page_config(page_title="SF Dump DB Viewer", layout="wide")
    st.title("SF Dump DB Viewer")

    # Sidebar: DB selection
    initial_db = _initial_db_path_from_argv()
    db_path_str = st.sidebar.text_input(
        "SQLite DB path",
        value=str(initial_db) if initial_db is not None else "",
        help="Path to sfdata.db created by 'sfdump build-db'.",
    )

    if not db_path_str:
        st.info("Enter a path to a sfdata.db file in the sidebar to get started.")
        return

    db_path = Path(db_path_str)

    try:
        overview = inspect_sqlite_db(db_path)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Unable to open or inspect DB at {db_path}: {exc}")
        return

    st.sidebar.markdown(f"**DB:** `{overview.path}`")
    st.sidebar.markdown(
        f"**Tables:** {len(overview.tables)}  |  **Indexes:** {overview.index_count}"
    )

    object_choices = _get_object_choices(overview.tables)
    if not object_choices:
        st.warning(
            "No known Salesforce objects found in this DB. "
            "Did you build it with 'sfdump build-db' from an export that included object CSVs?"
        )
        return

    api_name = st.sidebar.selectbox("Object", object_choices, index=0)

    search_term = st.sidebar.text_input(
        "Search (Name contains)",
        value="",
        help="Substring match on the Name field where present.",
    )
    limit = st.sidebar.number_input(
        "Max rows",
        min_value=1,
        max_value=1000,
        value=100,
        step=10,
    )

    regex_search = st.sidebar.checkbox(
        "Use regex (Name REGEXP)",
        value=False,
        help="When enabled, interpret the search string as a regular expression applied to the Name field.",
    )

    show_all_fields = st.sidebar.checkbox(
        "Show all fields",
        value=False,
        help="When checked, show all columns for this object. When unchecked, only show key fields.",
    )

    # Build WHERE clause for Name search
    where_clause: Optional[str] = None
    if search_term:
        # simple SQL escaping for single quotes
        safe_term = search_term.replace("'", "''")
        if regex_search:
            # Use our SQLite REGEXP function defined in record_list.py
            where_clause = f"Name REGEXP '{safe_term}'"
        else:
            # Default behaviour: substring match
            where_clause = f"Name LIKE '%{safe_term}%'"

    try:
        listing = list_records(
            db_path=db_path,
            api_name=api_name,
            where=where_clause,
            limit=int(limit),
            order_by="Name",
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error listing records for {api_name}: {exc}")
        return

    rows = listing.rows

    col_left, col_right = st.columns([2, 3])

    with col_left:
        st.subheader(f"{api_name} records")

        if not rows:
            st.info("No records found. Try adjusting the search or increasing the max rows.")
            selected_id = None
        else:
            # Show a small table
            import pandas as pd  # type: ignore[import-not-found]

            df = pd.DataFrame(rows)
            display_cols = _select_display_columns(api_name, df, show_all_fields)
            st.dataframe(df[display_cols])

            # Selection widget
            options = []
            for r in rows:
                rid = r.get("Id")
                label = r.get("Name") or rid or "(no Id)"
                options.append(f"{label} [{rid}]")
            selected_label = st.selectbox(
                "Select record",
                options,
                index=0,
            )
            # Extract Id from label
            if "[" in selected_label and selected_label.endswith("]"):
                selected_id = selected_label.rsplit("[", 1)[-1].rstrip("]")
            else:
                # Fallback: try to find by Name
                selected_id = rows[0].get("Id")

    with col_right:
        st.subheader("Record details & relationships")

        if not rows or not selected_id:
            st.info("Select a record on the left to see details and related records.")
            return

        try:
            record = get_record_with_children(
                db_path=db_path,
                api_name=api_name,
                record_id=selected_id,
                max_children_per_rel=50,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Error loading record {selected_id}: {exc}")
            return

        parent = record.parent
        st.markdown(
            f"**{parent.sf_object.api_name}** "
            f"`{parent.data.get('Name', '')}` "
            f"(`{parent.data.get(parent.sf_object.id_field, selected_id)}`)"
        )

        # Parent fields
        # Parent fields
        with st.expander("Parent fields", expanded=True):
            import pandas as pd  # type: ignore[import-not-found]

            # Turn the parent dict into a DataFrame
            all_items = sorted(parent.data.items())
            all_df = pd.DataFrame([{"Field": k, "Value": v} for k, v in all_items])

            if show_all_fields:
                parent_df = all_df
            else:
                important = _get_important_fields(parent.sf_object.api_name)
                if important:
                    parent_df = all_df[all_df["Field"].isin(important)]
                else:
                    # fallback: just show everything if we don't know what's important
                    parent_df = all_df

            st.table(parent_df)

        # Children
        if not record.children:
            st.info("No child records found for this record.")
            return

        for coll in record.children:
            child_obj = coll.sf_object
            rel = coll.relationship
            title = (
                f"{child_obj.api_name} via {rel.child_field} "
                f"(relationship: {rel.name}, {len(coll.records)} record(s))"
            )
            with st.expander(title, expanded=False):
                import pandas as pd  # type: ignore[import-not-found]

                child_df = pd.DataFrame(coll.records)
                display_cols = _select_display_columns(
                    child_obj.api_name, child_df, show_all_fields
                )
                st.dataframe(child_df[display_cols])


if __name__ == "__main__":
    main()
