#!/usr/bin/env python
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

SCRIPT_DIR = Path(__file__).resolve().parent


def guess_exports_base() -> Path:
    """Try to guess where the 'exports' root lives.

    Preference order:
      1. ~/OneDrive - Example Company/SF/exports
      2. <current working dir>/exports
      3. <repo>/exports (one level above scripts)
    """
    home = Path.home()
    candidates = [
        home / "OneDrive - Example Company" / "SF" / "exports",
        Path.cwd() / "exports",
        SCRIPT_DIR.parent / "exports",
    ]

    for c in candidates:
        if c.exists():
            return c.resolve()

    # Fallback to the first candidate even if it doesn't exist yet
    return candidates[0]


@st.cache_data
def load_master_index(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str).fillna("")
    # Helpful derived column for search
    df["search_blob"] = (
        df.get("file_name", "")
        + " "
        + df.get("record_name", "")
        + " "
        + df.get("object_type", "")
        + " "
        + df.get("account_name", "")
        + " "
        + df.get("opp_name", "")
    ).str.lower()
    return df


def resolve_file_path(export_root: Path, local_path: str) -> Path:
    """Resolve the on-disk path for a document.

    - If local_path is absolute and exists → return it.
    - If local_path is relative → first try export_root / local_path.
    - If nothing exists → return the original as a Path (will fail later).
    """
    p = Path(local_path)
    if p.is_absolute() and p.exists():
        return p

    if not p.is_absolute():
        candidate = (export_root / p).resolve()
        if candidate.exists():
            return candidate

    return p


def main() -> None:
    st.set_page_config(page_title="Salesforce Documents Browser", layout="wide")
    st.title("Salesforce Documents Browser")

    # ------------------------------------------------------------------
    # Sidebar: choose exports base + specific export run
    # ------------------------------------------------------------------
    st.sidebar.header("Location")

    default_exports_base = guess_exports_base()

    exports_base_str = st.sidebar.text_input(
        "Exports base directory (contains export-YYYY-MM-DD folders)",
        value=str(default_exports_base),
        help=(
            "This folder should contain subfolders like 'export-2025-11-15', "
            "each one being a full SF export with csv/, files/, meta/."
        ),
    )

    exports_base = Path(exports_base_str).expanduser().resolve()

    if not exports_base.exists():
        st.error(
            f"Exports folder not found:\n\n{exports_base}\n\n"
            "If this is your first time running the viewer, please run:\n"
            "`make export-all`\n"
            "to generate your first export."
        )
        st.stop()

    # Find export-* subdirectories
    run_dirs = sorted(
        [p for p in exports_base.iterdir() if p.is_dir() and p.name.startswith("export-")]
    )

    if not run_dirs:
        st.error(
            f"No 'export-YYYY-MM-DD' directories found under:\n{exports_base}\n\n"
            "Run 'make export-all' first to generate your first export."
        )
        st.stop()

    # Auto-detect the latest export directory
    latest_run = run_dirs[-1]

    st.sidebar.markdown(f"**Latest export detected:** `{latest_run.name}`")

    # Allow manual override, but default to latest
    selected_run_name = st.sidebar.selectbox(
        "Choose export run",
        options=[p.name for p in run_dirs],
        index=[p.name for p in run_dirs].index(latest_run.name),
    )

    export_root = exports_base / selected_run_name
    master_index_path = export_root / "meta" / "master_documents_index.csv"

    st.sidebar.write(f"Using export root: `{export_root}`")
    st.sidebar.write(f"Master index: `{master_index_path}`")

    if not master_index_path.exists():
        st.error(f"Master index not found at:\n{master_index_path}")
        st.stop()

    df = load_master_index(master_index_path)

    # ------------------------------------------------------------------
    # Sidebar: filters
    # ------------------------------------------------------------------
    st.sidebar.header("Filters")

    # Object types
    object_types = sorted(df["object_type"].dropna().unique())
    selected_types = st.sidebar.multiselect(
        "Object types",
        options=object_types,
        default=object_types,
    )

    # File extensions
    extensions = sorted([e for e in df.get("file_extension", "").dropna().unique() if e])
    selected_ext = st.sidebar.multiselect(
        "File extensions",
        options=extensions,
        default=extensions,
    )

    # Global search
    query = st.text_input(
        "Search (supports * wildcard; searches file, record, account, opp):",
        "",
    )

    # --- NEW: column-specific filters ---------------------------------
    col_filters: dict[str, str] = {}

    with st.sidebar.expander("More column filters", expanded=False):
        if "record_name" in df.columns:
            col_filters["record_name"] = st.text_input("Record name contains", "")
        if "account_name" in df.columns:
            col_filters["account_name"] = st.text_input("Account name contains", "")
        if "opp_name" in df.columns:
            col_filters["opp_name"] = st.text_input("Opportunity name contains", "")
        if "opp_stage" in df.columns:
            col_filters["opp_stage"] = st.text_input("Stage contains", "")
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Apply filters
    # ------------------------------------------------------------------
    mask = pd.Series(True, index=df.index)

    if selected_types:
        mask &= df["object_type"].isin(selected_types)

    if selected_ext:
        mask &= df["file_extension"].isin(selected_ext)

    if query:
        q = query.strip().lower()
        q = q.replace("*", "")  # allow * for convenience

        if q:
            mask &= df["search_blob"].str.contains(q, case=False, na=False)

    # Apply column-specific filters
    for col, value in col_filters.items():
        if value:
            mask &= df[col].str.contains(value, case=False, na=False)

    filtered = df[mask].copy()
    filtered_count = len(filtered)

    st.write(f"Showing up to 500 of {filtered_count:,} matching documents:")
    st.info(f"Displaying the first 500 of {filtered_count:,} matching documents.")

    # ----------------------------------------------------------------------
    # Columns to show (robust and future-proof)
    # ----------------------------------------------------------------------
    preferred_cols = [
        "file_source",
        "file_name",
        "file_extension",
        "object_type",
        "record_name",
        "account_name",
        "opp_name",
        "opp_stage",
        "opp_amount",
        "opp_close_date",
        "local_path",
    ]

    # Only use columns that actually exist
    available_cols = [col for col in preferred_cols if col in filtered.columns]

    if not available_cols:
        st.warning(
            "None of the expected index columns were found.\n"
            "This export may be incomplete or the index format has changed."
        )
        st.stop()

    # --- NEW: allow user to choose which columns to display ------------
    with st.sidebar.expander("Columns to display", expanded=False):
        show_cols = st.multiselect(
            "Select columns",
            options=available_cols,
            default=available_cols,
        )
    if not show_cols:
        show_cols = available_cols
    # ----------------------------------------------------------------------

    # ----------------------------------------------------------------------
    # Display the table
    # ----------------------------------------------------------------------
    display = filtered[show_cols].head(500)
    st.dataframe(display, width="stretch")

    # Success banner
    st.success(f"Viewer loaded successfully — {len(df):,} total documents indexed.")

    st.caption(
        "Tip: Narrow down with filters and search, "
        "then use the section below to open a specific document."
    )

    # ------------------------------------------------------------------
    # Open a specific document
    # ------------------------------------------------------------------
    st.subheader("Open a document")

    if "local_path" not in filtered.columns:
        st.warning(
            "This export does not include direct file paths.\n"
            "You can still browse the index, but document opening is unavailable."
        )
        st.stop()

    if filtered.empty:
        st.info("No matching documents. Adjust your filters/search.")
        return

    limited = filtered.head(200)

    options = [
        f"{row.file_name}  |  {row.object_type}  |  {row.record_name}"
        for _, row in limited.iterrows()
    ]

    choice = st.selectbox(
        "Select a document to open (limited to first 200 filtered results):",
        options=[""] + options,
    )

    if choice:
        idx = options.index(choice)
        row = limited.iloc[idx]
        local_path = row.get("local_path", "")

        if not local_path:
            st.warning(
                "No local file is available for this row.\n\n"
                "The master index knows a document was associated with this record, "
                "but no Attachment/File binary was exported (for example, because it "
                "doesn't exist anymore or is stored in a package-specific object)."
            )
            return

        full_path = resolve_file_path(export_root, local_path)

        if st.button(f"Open '{row.file_name}'"):
            if not full_path.exists():
                st.error(
                    f"File not found on disk:\n\n{full_path}\n\n"
                    "It may not have been downloaded or may have been moved."
                )
            else:
                try:
                    os.startfile(str(full_path))  # Windows
                    st.success(f"Opened file:\n{full_path}")
                except Exception as e:
                    st.error(f"Unable to open this file:\n{e}")


if __name__ == "__main__":
    main()
