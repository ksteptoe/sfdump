from __future__ import annotations

import sqlite3
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
    "ContentDocumentLink": [
        "Id",
        "LinkedEntityId",
        "ContentDocumentId",
        "DocumentTitle",
        "ShareType",
        "Visibility",
    ],
    "Attachment": ["Id", "ParentId", "Name", "ContentType", "BodyLength"],
    # 🧾 Generic finance shapes (kept in case you end up with these names)
    "Invoice": [
        "Id",
        "Name",  # if present
        "InvoiceNumber",
        "InvoiceDate",
        "Status",
        "TotalAmount",
        "Balance",
    ],
    "InvoiceLine": [
        "Id",
        "InvoiceId",
        "LineNumber",
        "ProductName",
        "Description",
        "Quantity",
        "UnitPrice",
        "Amount",
    ],
    "CreditNote": [
        "Id",
        "Name",
        "CreditNoteNumber",
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
    # Concrete Coda / FinancialForce objects from your export
    "c2g__codaInvoice__c": [
        "Id",
        "Name",  # invoice number (SIN001673 etc.)
        "CurrencyIsoCode",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__NetTotal__c",
        "c2g__OutstandingValue__c",
        "c2g__TaxTotal__c",
        "Days_Overdue__c",
        "c2g__AccountName__c",
        "c2g__CompanyReference__c",
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
        "Product2Id",
        "Quantity",
        "UnitPrice",
        "TotalPrice",
        "Description",
    ],
}


def _enrich_contentdocument_links_with_title(db_path: Path, df):
    """
    For ContentDocumentLink rows, add a 'DocumentTitle' column by looking up
    ContentDocument.Title from the 'content_document' table in the viewer DB.

    If anything goes wrong (no table, etc.), this falls back silently.
    """
    # Defensive: if the column isn't there, nothing to do
    if "ContentDocumentId" not in df.columns:
        return df

    # Collect distinct non-empty IDs
    doc_ids = {str(x) for x in df["ContentDocumentId"] if x}
    if not doc_ids:
        return df

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            cur = conn.cursor()
            placeholders = ", ".join("?" for _ in doc_ids)
            sql = f'SELECT "Id", "Title" FROM "content_document" WHERE Id IN ({placeholders})'
            cur.execute(sql, list(doc_ids))
            rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        # If the table doesn't exist or query fails, just return the original df
        return df

    # Build a mapping Id -> Title
    id_to_title = {row[0]: row[1] for row in rows}

    # Add a friendly column
    df = df.copy()
    df["DocumentTitle"] = df["ContentDocumentId"].map(id_to_title)
    return df


def _load_files_for_record(db_path: Path, parent_id: str) -> dict[str, list[dict[str, object]]]:
    """
    Look up files/attachments for a given Salesforce record Id in the viewer DB.

    We try:
      - Legacy Attachment records via Attachment.ParentId
      - ContentDocumentLink -> ContentDocument -> ContentVersion (latest version)
    If the relevant tables are missing, we just return empty lists.
    """
    results: dict[str, list[dict[str, object]]] = {
        "attachments": [],
        "content_docs": [],
    }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        # --- Legacy Attachments ---------------------------------------------
        try:
            cur.execute(
                """
                SELECT
                    Id,
                    Name,
                    ContentType,
                    BodyLength,
                    ParentId
                FROM Attachment
                WHERE ParentId = ?
                """,
                (parent_id,),
            )
            results["attachments"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            # Table doesn't exist in this DB – ignore
            pass

        # --- ContentDocumentLink / ContentDocument / ContentVersion ----------
        try:
            cur.execute(
                """
                SELECT
                    l.Id                AS LinkId,
                    l.ContentDocumentId AS ContentDocumentId,
                    l.LinkedEntityId    AS LinkedEntityId,
                    l.ShareType         AS ShareType,
                    l.Visibility        AS Visibility,
                    cd.Title            AS DocumentTitle,
                    cd.FileType         AS DocumentFileType,
                    cv.VersionNumber    AS VersionNumber,
                    cv.FileExtension    AS FileExtension,
                    cv.ContentSize      AS ContentSize
                FROM ContentDocumentLink AS l
                LEFT JOIN ContentDocument AS cd
                    ON cd.Id = l.ContentDocumentId
                LEFT JOIN ContentVersion AS cv
                    ON cv.ContentDocumentId = cd.Id
                   AND (cv.IsLatest = 1 OR cv.IsLatest IS NULL)
                WHERE l.LinkedEntityId = ?
                """,
                (parent_id,),
            )
            results["content_docs"] = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            # One or more of the tables doesn't exist – ignore
            pass

    finally:
        conn.close()

    return results


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
    # When launched via: streamlit run db_app.py -- <db-path>
    # sys.argv for this script will look like: ['db_app.py', '<db-path>']
    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)
    return None


def _get_object_choices(tables) -> list[tuple[str, str]]:
    """
    Return sorted (label, api_name) for objects that actually exist in the DB.

    Uses SFObject.label for friendliness, but keeps the API name visible.
    """
    table_names = {t.name for t in tables}
    choices: list[tuple[str, str]] = []

    for obj in OBJECTS.values():
        if obj.table_name in table_names:
            label = getattr(obj, "label", None) or obj.api_name
            if label != obj.api_name:
                ui_label = f"{label} ({obj.api_name})"
            else:
                ui_label = label
            choices.append((ui_label, obj.api_name))

    return sorted(choices, key=lambda x: x[0])


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

    labels = [label for (label, _api) in object_choices]
    label_to_api = {label: api for (label, api) in object_choices}

    selected_label = st.sidebar.selectbox("Object", labels, index=0)
    api_name = label_to_api[selected_label]

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
        st.subheader(f"{selected_label} records")

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
            selected_label_value = st.selectbox(
                "Select record",
                options,
                index=0,
            )
            # Extract Id from label
            if "[" in selected_label_value and selected_label_value.endswith("]"):
                selected_id = selected_label_value.rsplit("[", 1)[-1].rstrip("]")
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
        parent_label = getattr(parent.sf_object, "label", None) or parent.sf_object.api_name

        st.markdown(
            f"**{parent_label}** "
            f"`{parent.data.get('Name', '')}` "
            f"(`{parent.data.get(parent.sf_object.id_field, selected_id)}`)"
        )

        # Files & attachments (if any) for this record
        import pandas as pd  # type: ignore[import-not-found]

        files = _load_files_for_record(db_path, selected_id)
        if files["attachments"] or files["content_docs"]:
            with st.expander("Files & attachments", expanded=False):
                if files["attachments"]:
                    st.markdown("**Legacy Attachments**")
                    st.dataframe(pd.DataFrame(files["attachments"]))

                if files["content_docs"]:
                    st.markdown("**Content Documents (via ContentDocumentLink)**")
                    st.dataframe(pd.DataFrame(files["content_docs"]))

        # Parent fields
        with st.expander("Parent fields", expanded=True):
            import pandas as pd  # type: ignore[import-not-found]

            all_items = sorted(parent.data.items())
            all_df = pd.DataFrame([{"Field": k, "Value": v} for k, v in all_items])

            if show_all_fields:
                parent_df = all_df
            else:
                important = _get_important_fields(parent.sf_object.api_name)
                if important:
                    parent_df = all_df[all_df["Field"].isin(important)]
                else:
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

                # Special case: for ContentDocumentLink, look up ContentDocument.Title
                if child_obj.api_name == "ContentDocumentLink":
                    child_df = _enrich_contentdocument_links_with_title(db_path, child_df)

                display_cols = _select_display_columns(
                    child_obj.api_name, child_df, show_all_fields
                )
                st.dataframe(child_df[display_cols])


if __name__ == "__main__":
    main()
