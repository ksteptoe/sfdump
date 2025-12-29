from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import streamlit as st

from sfdump.viewer_app.services.display import get_important_fields
from sfdump.viewer_app.services.nav import breadcrumbs, peek, pop, push, reset


@dataclass
class SidebarState:
    db_path: Path
    api_name: str
    selected_id: str
    selected_label: str
    search_term: str
    limit: int
    regex_search: bool
    show_all_fields: bool
    show_ids: bool


def _list_tables(db_path: Path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    hidden_prefixes = ("sqlite_",)
    hidden_exact = {"record_documents"}
    out: list[str] = []
    for t in tables:
        if t in hidden_exact:
            continue
        if any(t.startswith(p) for p in hidden_prefixes):
            continue
        out.append(t)
    return out


def _guess_api_from_table(table: str) -> str:
    if "__" in table:
        return table
    return table[:1].upper() + table[1:]


def render_sidebar_controls(
    initial_db: Path | None = None,
    db_path: Path | None = None,
    *,
    default_api_name: Optional[str] = None,
    default_record_id: Optional[str] = None,
) -> Optional[SidebarState]:
    effective_db = db_path or initial_db
    if effective_db is None:
        st.sidebar.error("No DB path provided.")
        return None

    return render_sidebar(
        Path(effective_db),
        default_api_name=default_api_name,
        default_record_id=default_record_id,
    )


def render_sidebar(
    db_path: Path,
    *,
    default_api_name: Optional[str] = None,
    default_record_id: Optional[str] = None,
) -> Optional[SidebarState]:
    st.sidebar.header("Viewer")

    if not db_path.exists():
        st.sidebar.error(f"DB not found: {db_path}")
        return None

    tables = _list_tables(db_path)
    if not tables:
        st.sidebar.error("No tables found in DB.")
        return None

    api_options = [_guess_api_from_table(t) for t in tables]
    api_default = default_api_name if default_api_name in api_options else api_options[0]
    api_name = st.sidebar.selectbox("Object", api_options, index=api_options.index(api_default))

    search_term = st.sidebar.text_input("Search", value="")
    regex_search = st.sidebar.checkbox("Regex search", value=False)

    limit = int(
        st.sidebar.number_input(
            "Limit",
            min_value=10,
            max_value=5000,
            value=200,
            step=50,
        )
    )

    show_all_fields = st.sidebar.checkbox("Show all fields", value=False)
    show_ids = st.sidebar.checkbox("Show Id columns", value=False)

    st.sidebar.divider()
    bc = breadcrumbs()
    if bc:
        st.sidebar.caption("Navigation")
        for i, item in enumerate(bc):
            label = item.label or item.record_id
            if st.sidebar.button(f"{item.api_name}: {label}", key=f"nav_jump_{i}"):
                push(item.api_name, item.record_id, label=item.label)
                st.rerun()

        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("Back"):
                pop()
                st.rerun()
        with c2:
            if st.sidebar.button("Reset"):
                reset()
                st.rerun()

    current = peek()
    selected_id = ""
    selected_label = ""

    if current:
        api_name = current.api_name
        selected_id = current.record_id
        selected_label = current.label or current.record_id
    elif default_record_id:
        selected_id = default_record_id
        selected_label = default_record_id

    return SidebarState(
        db_path=Path(db_path),
        api_name=api_name,
        selected_id=selected_id,
        selected_label=selected_label,
        search_term=search_term,
        limit=limit,
        regex_search=regex_search,
        show_all_fields=show_all_fields,
        show_ids=show_ids,
    )


def render_record_list(
    *,
    db_path: Path,
    api_name: str,
    selected_label: str | None = None,
    search_term: str = "",
    limit: int = 200,
    regex_search: bool = False,
    show_all_fields: bool = False,
    show_ids: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """
    Render the record list and return (rows, selected_id).
    Accepts show_all_fields/show_ids so db_app can pass them without breaking.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        def table_exists(t: str) -> bool:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,))
            return cur.fetchone() is not None

        table = (
            api_name
            if table_exists(api_name)
            else (api_name.lower() if table_exists(api_name.lower()) else None)
        )
        if not table:
            st.warning(f"No table found for object `{api_name}` in this DB.")
            return ([], "")

        cur.execute(f'PRAGMA table_info("{table}")')
        cols = [r[1] for r in cur.fetchall()]
        if "Id" not in cols:
            st.warning(f"Table `{table}` has no Id column.")
            return ([], "")

        important = [c for c in get_important_fields(api_name) if c in cols]
        label_candidates = [c for c in ["Name", "Subject", "Title", "DocumentTitle"] if c in cols]

        fetch_cols = ["Id"]
        if show_all_fields:
            fetch_cols = cols[:]  # everything
        else:
            for c in important + label_candidates:
                if c not in fetch_cols:
                    fetch_cols.append(c)

        # Keep list query light
        select_sql = ", ".join([f'"{c}"' for c in fetch_cols])

        term = (search_term or "").strip()
        rows: list[dict[str, Any]] = []

        if term and label_candidates and not regex_search:
            like_cols = label_candidates[:3]
            where = " OR ".join([f'"{c}" LIKE ?' for c in like_cols])
            params = [f"%{term}%"] * len(like_cols)
            sql = f'SELECT {select_sql} FROM "{table}" WHERE ({where}) LIMIT ?'
            cur.execute(sql, (*params, int(limit)))
            rows = [dict(r) for r in cur.fetchall()]
        else:
            sql = f'SELECT {select_sql} FROM "{table}" LIMIT ?'
            cur.execute(sql, (int(max(limit, 200)),))
            rows = [dict(r) for r in cur.fetchall()]

            if term:
                if regex_search:
                    try:
                        rx = re.compile(term, re.IGNORECASE)
                    except re.error:
                        rx = None

                    def match(r: dict[str, Any]) -> bool:
                        hay = " ".join(
                            str(r.get(c, "") or "") for c in (label_candidates + important + ["Id"])
                        )
                        return bool(rx.search(hay)) if rx else (term.lower() in hay.lower())
                else:

                    def match(r: dict[str, Any]) -> bool:
                        hay = " ".join(
                            str(r.get(c, "") or "") for c in (label_candidates + important + ["Id"])
                        )
                        return term.lower() in hay.lower()

                rows = [r for r in rows if match(r)][: int(limit)]
            else:
                rows = rows[: int(limit)]

        if not rows:
            st.info("No records found.")
            return ([], "")

        def id_from_label(label: str) -> str:
            s = (label or "").strip()
            if s.endswith("]") and "[" in s:
                return s.rsplit("[", 1)[-1].rstrip("]").strip()
            return ""

        def label_row(r: dict[str, Any]) -> str:
            parts: list[str] = []
            for c in important:
                v = str(r.get(c, "") or "").strip()
                if v:
                    parts.append(v)
            if not parts:
                for c in label_candidates:
                    v = str(r.get(c, "") or "").strip()
                    if v:
                        parts.append(v)
                        break

            rid = str(r.get("Id", "") or "").strip()
            base = " — ".join(parts) if parts else rid
            if show_ids or not base:
                return f"{base} [{rid}]" if rid else base
            return base

        labels = [label_row(r) for r in rows]

        default_index = 0
        if selected_label:
            sel = str(selected_label).strip()
            sel_id = id_from_label(sel) or sel
            for i, lab in enumerate(labels):
                if lab == sel:
                    default_index = i
                    break
                if sel_id and id_from_label(lab) == sel_id:
                    default_index = i
                    break

        choice = st.selectbox(
            "Records", options=labels, index=default_index, key=f"record_list_{api_name}"
        )
        selected_id = id_from_label(choice) or ""
        return (rows, selected_id)
    finally:
        conn.close()
