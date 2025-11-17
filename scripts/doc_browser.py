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
      1. ~/OneDrive - Sondrel Ltd/SF/exports
      2. <current working dir>/exports
      3. <repo>/exports (one level above scripts)
    """
    home = Path.home()
    candidates = [
        home / "OneDrive - Sondrel Ltd" / "SF" / "exports",
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
        st.error(f"Exports base directory does not exist:\n{exports_base}")
        st.stop()

    # Find export-* subdirectories
    run_dirs = sorted(
        [p for p in exports_base.iterdir() if p.is_dir() and p.name.startswith("export-")]
    )

    if not run_dirs:
        st.error(f"No 'export-YYYY-MM-DD' directories found under:\n{exports_base}")
        st.stop()

    # Default to the latest (lexicographically last)
    default_run = run_dirs[-1].name

    selected_run_name = st.sidebar.selectbox(
        "Export run",
        options=[p.name for p in run_dirs],
        index=[p.name for p in run_dirs].index(default_run),
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

    # Search box
    query = st.text_input(
        "Search (supports * wildcard; searches file, record, account, opp):",
        "",
    )

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
        if "*" in q:
            q = q.replace("*", "")
        if q:
            mask &= df["search_blob"].str.contains(q, na=False)

    filtered = df[mask].copy()
    filtered_count = len(filtered)

    st.write(f"Showing up to 500 of {filtered_count:,} matching documents:")

    # Columns to show
    show_cols = [
        c
        for c in [
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
        if c in filtered.columns
    ]

    display = filtered[show_cols].head(500)
    st.dataframe(display, use_container_width=True)

    st.caption(
        "Tip: Narrow down with filters and search, "
        "then use the section below to open a specific document."
    )

    # ------------------------------------------------------------------
    # Open a specific document
    # ------------------------------------------------------------------
    st.subheader("Open a document")

    if "local_path" not in filtered.columns:
        st.info("No local_path column in index; cannot open files directly.")
        return

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
            st.error("This row has an empty local_path.")
            return

        full_path = resolve_file_path(export_root, local_path)

        if st.button(f"Open: {row.file_name}"):
            if full_path.exists():
                try:
                    # Windows: open with default associated app
                    os.startfile(str(full_path))  # type: ignore[attr-defined]
                    st.success(f"Opened: {full_path}")
                except Exception as e:
                    st.error(f"Failed to open file: {e}")
            else:
                st.error(f"File not found on disk:\n{full_path}")


if __name__ == "__main__":
    main()
