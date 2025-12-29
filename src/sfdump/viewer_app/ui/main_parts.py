from __future__ import annotations

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
        effective_db,
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

    if not Path(db_path).exists():
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

    # Navigation controls
    st.sidebar.divider()
    bc = breadcrumbs()
    if bc:
        st.sidebar.caption("Navigation")
        for i, item in enumerate(bc):
            label = item.label or item.record_id
            if st.sidebar.button(f"{item.api_name}: {label}", key=f"nav_jump_{i}"):
                push(item.api_name, item.record_id, label=item.label)
                st.rerun()

        cols = st.sidebar.columns(2)
        if cols[0].button("Back", use_container_width=True):
            pop()
            st.rerun()
        if cols[1].button("Reset", use_container_width=True):
            reset()
            st.rerun()

    current = peek()
    selected_id = ""
    selected_label = ""

    if current:
        api_name = current.api_name
        selected_id = current.record_id
        selected_label = current.label or current.record_id
    else:
        if default_record_id:
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
    show_all_fields: bool = False,  # accepted for API compatibility
    show_ids: bool = False,
) -> tuple[list[dict[str, Any]], str]:
    """
    Render the record picker and return (rows, selected_id).

    Robust behaviour: the selectbox OPTION is the record Id, and the display label
    is provided via format_func. This avoids brittle parsing of Ids from strings.
    """
    import re

    def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cur.fetchone() is not None

    def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
        cur.execute(f'PRAGMA table_info("{table}")')
        return [r[1] for r in cur.fetchall()]

    def _pick_table(cur: sqlite3.Cursor, name: str) -> str | None:
        for t in (name, name.lower()):
            if _table_exists(cur, t):
                return t
        return None

    def _try_extract_id(text: str) -> str:
        s = (text or "").strip()
        if s.endswith("]") and "[" in s:
            return s.rsplit("[", 1)[-1].rstrip("]").strip()
        return ""

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        table = _pick_table(cur, api_name)
        if not table:
            st.warning(f"No table found for object `{api_name}` in this DB.")
            return ([], "")

        cols = _table_columns(cur, table)
        if "Id" not in cols:
            st.warning(f"Table `{table}` has no Id column.")
            return ([], "")

        label_candidates = ["Name", "Subject", "Title", "DocumentTitle"]
        label_cols = [c for c in label_candidates if c in cols]

        important = [c for c in get_important_fields(api_name) if c in cols]

        fetch_cols = ["Id"]
        for c in important + label_cols:
            if c not in fetch_cols:
                fetch_cols.append(c)

        select_sql = ", ".join([f'"{c}"' for c in fetch_cols])

        term = (search_term or "").strip()
        rows: list[dict[str, Any]]

        if term and label_cols and not regex_search:
            like_cols = label_cols[:3]
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
                        st.warning("Invalid regex; falling back to plain contains.")
                        rx = None

                    def _match(r: dict[str, Any]) -> bool:
                        hay = " ".join(
                            str(r.get(c, "") or "") for c in (label_cols + important + ["Id"])
                        )
                        return bool(rx.search(hay)) if rx else (term.lower() in hay.lower())
                else:

                    def _match(r: dict[str, Any]) -> bool:
                        hay = " ".join(
                            str(r.get(c, "") or "") for c in (label_cols + important + ["Id"])
                        )
                        return term.lower() in hay.lower()

                rows = [r for r in rows if _match(r)][: int(limit)]
            else:
                rows = rows[: int(limit)]

        if not rows:
            st.info("No records found.")
            return ([], "")

        # id list + label map
        ids: list[str] = []
        label_map: dict[str, str] = {}

        for r in rows:
            rid = str(r.get("Id", "") or "").strip()
            if not rid:
                continue

            parts: list[str] = []
            for c in important:
                v = str(r.get(c, "") or "").strip()
                if v:
                    parts.append(v)

            if not parts:
                for c in label_cols:
                    v = str(r.get(c, "") or "").strip()
                    if v:
                        parts.append(v)
                        break

            base_label = " — ".join(parts) if parts else rid
            label = f"{base_label} [{rid}]" if show_ids else base_label

            ids.append(rid)
            label_map[rid] = label

        if not ids:
            st.info("No records found.")
            return (rows, "")

        # Determine default selection
        default_index = 0
        if selected_label:
            sel = str(selected_label).strip()
            sel_id = _try_extract_id(sel) or sel
            if sel_id in ids:
                default_index = ids.index(sel_id)
            else:
                # match by label text
                for i, rid in enumerate(ids):
                    if label_map.get(rid, "") == sel:
                        default_index = i
                        break

        selected_id = st.selectbox(
            "Records",
            options=ids,
            index=default_index,
            key=f"record_list_{api_name}",
            format_func=lambda rid: label_map.get(str(rid), str(rid)),
        )

        return (rows, str(selected_id))

    finally:
        conn.close()
