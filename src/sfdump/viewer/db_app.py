from __future__ import annotations

import base64
import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

import streamlit as st
import streamlit.components.v1 as components

from sfdump.indexing import OBJECTS
from sfdump.viewer import get_record_with_children, inspect_sqlite_db, list_records
from sfdump.viewer_app.preview.files import open_local_file, preview_file
from sfdump.viewer_app.preview.pdf import preview_pdf_bytes
from sfdump.viewer_app.services.content import enrich_contentdocument_links_with_title
from sfdump.viewer_app.services.display import get_important_fields, select_display_columns
from sfdump.viewer_app.services.documents import list_record_documents, load_master_documents_index
from sfdump.viewer_app.services.objects import get_object_choices
from sfdump.viewer_app.services.paths import (
    infer_export_root,
    resolve_export_path,
)
from sfdump.viewer_app.services.traversal import collect_subtree_ids


def _render_pdf_inline(pdf_bytes: bytes, *, height: int = 900) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    html = f"""
    <iframe
        src="data:application/pdf;base64,{b64}"
        width="100%"
        height="{height}"
        style="border: 1px solid #ddd; border-radius: 8px;"
    ></iframe>
    """
    components.html(html, height=height + 20, scrolling=True)


def _export_root_from_db_path(db_path: Path) -> Optional[Path]:
    """
    Best-effort: infer EXPORT_ROOT from db_path.
    Typical layout: EXPORT_ROOT/meta/sfdata.db
    """
    return infer_export_root(db_path)


def _pdf_preview_pdfjs(pdf_bytes: bytes, *, height: int = 750) -> None:
    """
    Render PDF inline using PDF.js (avoids Chrome blocking the built-in PDF viewer in iframes).
    Requires internet access to load pdf.js from CDN.
    """
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    html = f"""
    <div style="width:100%; height:{height}px; overflow:auto; border:1px solid #ddd; border-radius:8px; padding:8px;">
      <div style="margin-bottom:8px; display:flex; gap:8px; align-items:center;">
        <button id="prev">Prev</button>
        <button id="next">Next</button>
        <span style="font-family: sans-serif; font-size: 13px;">
          Page: <span id="page_num"></span> / <span id="page_count"></span>
        </span>
      </div>
      <canvas id="the-canvas" style="width:100%;"></canvas>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.10.38/pdf.min.js"></script>
    <script>
      (function() {{
        const b64 = "{b64}";
        const binary = atob(b64);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {{
          bytes[i] = binary.charCodeAt(i);
        }}

        const loadingTask = pdfjsLib.getDocument({{ data: bytes }});

        let pdf = null;
        let pageNum = 1;
        let pageRendering = false;
        let pageNumPending = null;

        const canvas = document.getElementById("the-canvas");
        const ctx = canvas.getContext("2d");

        function renderPage(num) {{
          pageRendering = true;
          pdf.getPage(num).then(function(page) {{
            const containerWidth = canvas.parentElement.clientWidth - 20;
            const viewport0 = page.getViewport({{ scale: 1.0 }});
            const scale = containerWidth / viewport0.width;
            const viewport = page.getViewport({{ scale: scale }});

            canvas.height = viewport.height;
            canvas.width = viewport.width;

            const renderTask = page.render({{ canvasContext: ctx, viewport: viewport }});
            renderTask.promise.then(function() {{
              pageRendering = false;
              document.getElementById("page_num").textContent = pageNum;

              if (pageNumPending !== null) {{
                renderPage(pageNumPending);
                pageNumPending = null;
              }}
            }});
          }});
        }}

        function queueRenderPage(num) {{
          if (pageRendering) {{
            pageNumPending = num;
          }} else {{
            renderPage(num);
          }}
        }}

        document.getElementById("prev").addEventListener("click", function() {{
          if (pageNum <= 1) return;
          pageNum--;
          queueRenderPage(pageNum);
        }});

        document.getElementById("next").addEventListener("click", function() {{
          if (pageNum >= pdf.numPages) return;
          pageNum++;
          queueRenderPage(pageNum);
        }});

        loadingTask.promise.then(function(loadedPdf) {{
          pdf = loadedPdf;
          document.getElementById("page_count").textContent = pdf.numPages;
          document.getElementById("page_num").textContent = pageNum;
          renderPage(pageNum);
        }});
      }})();
    </script>
    """

    st.components.v1.html(html, height=height + 40, scrolling=True)


def _pdf_iframe(path: Path, height: int = 750) -> None:
    pdf_bytes = path.read_bytes()
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    html = f"""
    <iframe
        src="data:application/pdf;base64,{b64}"
        width="100%"
        height="{height}"
        style="border: none;"
    ></iframe>
    """
    st.components.v1.html(html, height=height, scrolling=True)


def _pdf_iframe_bytes(pdf_bytes: bytes, height: int = 750) -> None:
    # Chrome often blocks data:application/pdf;base64,... in iframes.
    # Workaround: create a Blob in JS and iframe the blob: URL instead.
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    html = f"""
    <iframe id="pdf_frame" style="width:100%; height:{height}px; border:none;"></iframe>
    <script>
      (function() {{
        const b64 = "{b64}";
        const binary = atob(b64);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {{
          bytes[i] = binary.charCodeAt(i);
        }}
        const blob = new Blob([bytes], {{ type: "application/pdf" }});
        const url = URL.createObjectURL(blob);
        document.getElementById("pdf_frame").src = url;
      }})();
    </script>
    """
    st.components.v1.html(html, height=height, scrolling=True)


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


def _initial_db_path_from_argv() -> Optional[Path]:
    # When launched via: streamlit run db_app.py -- <db-path>
    # sys.argv for this script will look like: ['db_app.py', '<db-path>']
    args = sys.argv[1:]
    for arg in args:
        if not arg.startswith("-"):
            return Path(arg)
    return None


def _resolve_export_path(export_root: Path, rel_path: str) -> Path:
    return resolve_export_path(export_root, rel_path)


def main() -> None:
    st.set_page_config(page_title="SF Dump DB Viewer", layout="wide")
    st.markdown(
        """
        <style>
          /* overall app font */
          html, body, [class*="css"]  { font-size: 13px; }

          /* tighten padding */
          .block-container { padding-top: 1rem; padding-bottom: 1rem; }
          section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }

          /* dataframes: smaller text */
          div[data-testid="stDataFrame"] { font-size: 12px; }

          /* expander headers a bit smaller */
          details summary { font-size: 13px; }

          /* shrink selectbox / inputs slightly */
          .stSelectbox, .stTextInput, .stNumberInput, .stCheckbox { font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

    object_choices = get_object_choices(overview.tables)
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
            display_cols = select_display_columns(api_name, df, show_all_fields)
            st.dataframe(df[display_cols], height=260, hide_index=True, width="stretch")

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
        except Exception as exc:
            st.error(f"Error loading record {selected_id}: {exc}")
            return

        parent = record.parent
        parent_label = getattr(parent.sf_object, "label", None) or parent.sf_object.api_name

        import pandas as pd  # type: ignore[import-not-found]

        tab_details, tab_children, tab_docs = st.tabs(["Details", "Children", "Documents"])

        with tab_details:
            st.markdown(
                f"**{parent_label}** "
                f"`{parent.data.get('Name', '')}` "
                f"(`{parent.data.get(parent.sf_object.id_field, selected_id)}`)"
            )

            with st.expander("Parent fields", expanded=True):
                all_items = sorted(parent.data.items())
                all_df = pd.DataFrame([{"Field": k, "Value": v} for k, v in all_items])

                if show_all_fields:
                    parent_df = all_df
                else:
                    important = get_important_fields(parent.sf_object.api_name)
                    parent_df = all_df[all_df["Field"].isin(important)] if important else all_df

                st.table(parent_df)

        with tab_children:
            if not record.children:
                st.info("No child records found for this record.")
            else:
                for coll in record.children:
                    child_obj = coll.sf_object
                    rel = coll.relationship
                    title = (
                        f"{child_obj.api_name} via {rel.child_field} "
                        f"(relationship: {rel.name}, {len(coll.records)} record(s))"
                    )
                    with st.expander(title, expanded=False):
                        child_df = pd.DataFrame(coll.records)

                        if child_df.empty:
                            st.info("No rows.")
                        else:
                            if child_obj.api_name == "ContentDocumentLink":
                                child_df = enrich_contentdocument_links_with_title(
                                    db_path, child_df
                                )

                            display_cols = select_display_columns(
                                child_obj.api_name, child_df, show_all_fields
                            )
                            st.dataframe(
                                child_df[display_cols],
                                width="stretch",
                                hide_index=True,
                                height=260,
                            )

        with tab_docs:
            export_root = _export_root_from_db_path(db_path)
            if export_root is None:
                # Keep the UI usable even if we can't infer export root
                st.warning(
                    "Could not infer EXPORT_ROOT from DB path. "
                    "Expected EXPORT_ROOT/meta/sfdata.db layout."
                )
                st.stop()

            docs = list_record_documents(
                db_path=db_path,
                object_type=api_name,  # IMPORTANT: this matches record_documents.object_type
                record_id=selected_id,
            )

            if not docs:
                st.info("No documents indexed for this record.")
            else:
                docs_df = pd.DataFrame(docs)

                # Show a compact table
                show_cols = [
                    c
                    for c in [
                        "file_source",
                        "file_id",
                        "file_name",
                        "file_extension",
                        "path",
                        "size_bytes",
                        "content_type",
                    ]
                    if c in docs_df.columns
                ]
                st.dataframe(docs_df[show_cols], width="stretch", hide_index=True, height=260)

                # Pick one to open
                def _label(row: dict[str, Any]) -> str:
                    name = row.get("file_name") or "(no name)"
                    fid = row.get("file_id") or ""
                    return f"{name} [{fid}]"

                options = [_label(r) for r in docs]
                choice = st.selectbox("Select a document", options, index=0)

                chosen = docs[options.index(choice)]
                rel_path = str(chosen.get("path") or "")
                if not rel_path:
                    st.warning(
                        "This row has no local path. That usually means the file wasn’t downloaded into the export."
                    )
                else:
                    full_path = _resolve_export_path(export_root, rel_path)

                    cols = st.columns([1, 3])
                    with cols[0]:
                        if st.button("Open"):
                            if full_path.exists():
                                open_local_file(full_path)
                                st.success("Opened locally.")
                            else:
                                st.error(f"File not found on disk: {full_path}")

                    with cols[1]:
                        st.caption(str(full_path))

                    # --- inline preview / download ---
                    if full_path.exists():
                        data = full_path.read_bytes()
                        download_name = full_path.name
                        mime = chosen.get("content_type") or "application/octet-stream"

                        # Preview (PDF + images)
                        ext = full_path.suffix.lower()

                        if ext == ".pdf":
                            with st.expander("Preview PDF", expanded=True):
                                preview_pdf_bytes(data, height=750)

                        elif str(mime).startswith("image/"):
                            with st.expander("Preview image", expanded=True):
                                st.image(data, caption=download_name)

                        st.download_button(
                            "Download",
                            data=data,
                            file_name=download_name,
                            mime=str(mime),
                        )
                    else:
                        st.error(f"File not found on disk: {full_path}")

        # ------------------------------------------------------------------
        # Recursive subtree document search (Account -> Opp -> Invoice -> ...)
        # ------------------------------------------------------------------
        with st.expander("Recursive documents (subtree)", expanded=True):
            export_root = _export_root_from_db_path(db_path)
            if export_root is None:
                st.warning(
                    "Could not infer EXPORT_ROOT from DB path. "
                    "Expected EXPORT_ROOT/meta/sfdata.db layout."
                )
                st.stop()

            st.caption(f"Export root inferred as: {export_root}")

            # Controls
            max_depth = st.slider("Max traversal depth", 1, 6, 3, 1)
            max_children = st.slider("Max children per relationship", 10, 500, 100, 10)

            # Optional object filter (useful once this gets big)
            allow_filter = st.checkbox("Filter to specific object types", value=False)
            allow_objects: Optional[set[str]] = None
            if allow_filter:
                # Offer choices from OBJECTS registry
                all_api_names = sorted(OBJECTS.keys())
                selected = st.multiselect(
                    "Allowed objects",
                    options=all_api_names,
                    default=["Opportunity", "c2g__codaInvoice__c", "fferpcore__BillingDocument__c"],
                )
                allow_objects = set(selected)

            subtree = collect_subtree_ids(
                db_path=db_path,
                root_api=api_name,
                root_id=selected_id,
                max_depth=int(max_depth),
                max_children_per_rel=int(max_children),
                allow_objects=allow_objects,
            )

            total_records = sum(len(v) for v in subtree.values())
            st.write(
                f"Records in subtree: **{total_records}** across **{len(subtree)}** object types."
            )
            st.write({k: len(v) for k, v in sorted(subtree.items(), key=lambda x: -len(x[1]))})

            docs_df = load_master_documents_index(export_root)
            if docs_df is None:
                st.error(
                    "meta/master_documents_index.csv not found. "
                    "Run: `sfdump docs-index --export-root <EXPORT_ROOT>` "
                    "(or `make -f Makefile.export export-doc-index`)."
                )
                st.stop()

            # Filter docs by record_id in subtree
            all_ids: set[str] = set()
            for ids in subtree.values():
                all_ids.update(ids)

            # master index keys on record_id
            sub_docs = docs_df[docs_df["record_id"].isin(list(all_ids))].copy()

            st.write(f"Documents found: **{len(sub_docs)}**")

            if len(sub_docs) == 0:
                st.info("No documents attached to any record in the subtree.")
                st.stop()

            # Nice defaults for display
            show_cols = [
                "file_extension",
                "file_source",
                "file_name",
                "local_path",
                "object_type",
                "record_name",
                "account_name",
                "opp_name",
                "opp_stage",
                "opp_amount",
                "opp_close_date",
            ]
            show_cols = [c for c in show_cols if c in sub_docs.columns]

            st.dataframe(sub_docs[show_cols], height=260, hide_index=True, width="stretch")

            # Select + preview
            choices = []
            for _, r in sub_docs.iterrows():
                lp = r.get("local_path", "")
                fn = r.get("file_name", "")
                rn = r.get("record_name", "")
                ot = r.get("object_type", "")
                rid = r.get("record_id", "")
                label = f"{fn} — {ot}:{rn} [{rid}] :: {lp}"
                choices.append(label)

            selected_doc = st.selectbox("Preview a document", choices, index=0)
            # local_path is after ':: '
            local_path = selected_doc.rsplit("::", 1)[-1].strip()
            if local_path:
                preview_file(export_root, local_path)


if __name__ == "__main__":
    main()
