from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd
import streamlit as st

from sfdump.viewer_app.preview.files import preview_file
from sfdump.viewer_app.services.documents import list_record_documents
from sfdump.viewer_app.services.nav import push
from sfdump.viewer_app.services.paths import infer_export_root


def render_record_tabs(
    *,
    db_path: Path,
    api_name: str,
    record: Dict[str, Any],
    children: Dict[str, Any],
) -> None:
    tabs = st.tabs(["Details", "Children", "Documents"])

    with tabs[0]:
        st.subheader("Record")
        st.json(record, expanded=False)

    with tabs[1]:
        st.subheader("Related records")
        if not children:
            st.info("No children found.")
        else:
            # children is expected to be a dict of object -> list[dict]
            for child_api, items in children.items():
                st.markdown(f"### {child_api} ({len(items)})")
                if not items:
                    continue
                df = pd.DataFrame(items)
                st.dataframe(df, hide_index=True, width="stretch", height=220)

                # Optional: allow navigation into a child record if it has an Id
                if "Id" in df.columns:
                    ids = [x for x in df["Id"].astype(str).tolist() if x]
                    if ids:
                        chosen = st.selectbox(
                            f"Open {child_api} record",
                            options=ids,
                            key=f"child_open_{api_name}_{child_api}",
                        )
                        if st.button(f"Go to {child_api}", key=f"go_{api_name}_{child_api}"):
                            push(child_api, chosen, label=chosen)
                            st.rerun()

    with tabs[2]:
        st.subheader("Documents")
        export_root = infer_export_root(db_path)

        docs = list_record_documents(
            db_path=db_path,
            object_type=api_name,
            record_id=str(record.get("Id", "")),
            limit=500,
        )
        if not docs:
            st.info("No documents found for this record.")
            return

        df = pd.DataFrame(docs)
        st.dataframe(df, hide_index=True, width="stretch", height=260)

        choices = []
        for _, r in df.iterrows():
            lp = r.get("local_path", "")
            fn = r.get("file_name", "")
            rn = r.get("record_name", "")
            ot = r.get("object_type", "")
            rid = r.get("record_id", "")
            label = f"{fn} — {ot}:{rn} [{rid}] :: {lp}"
            choices.append(label)

        selected_doc = st.selectbox("Preview a document", choices, index=0)
        local_path = selected_doc.rsplit("::", 1)[-1].strip()
        if local_path:
            preview_file(export_root, local_path)
