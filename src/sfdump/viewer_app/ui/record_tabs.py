from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from sfdump.viewer_app.services.display import select_display_columns
from sfdump.viewer_app.services.nav import push


def _id_from_label(label: str) -> str:
    s = (label or "").strip()
    if s.endswith("]") and "[" in s:
        return s.rsplit("[", 1)[-1].rstrip("]").strip()
    return ""


def render_children_with_navigation(
    *,
    record: Any,
    show_all_fields: bool,
    show_ids: bool,
) -> None:
    """
    Renders the Children tab with an explicit "pick child -> Open" mechanism.

    Expects `record` to be the return of get_record_with_children().
    """
    if not getattr(record, "children", None):
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
            child_df = pd.DataFrame(coll.records)

            if child_df.empty:
                st.info("No rows.")
                continue

            # Build labels for selection
            label_cols = [c for c in ["Name", "Subject", "Title"] if c in child_df.columns]
            has_id = "Id" in child_df.columns

            labels: list[str] = []
            ids: list[str] = []
            for _, r in child_df.iterrows():
                rid = str(r.get("Id", "") if has_id else "").strip()
                lab = ""
                for c in label_cols:
                    v = str(r.get(c, "") or "").strip()
                    if v:
                        lab = v
                        break
                if lab and rid:
                    labels.append(f"{lab} [{rid}]")
                elif rid:
                    labels.append(rid)
                else:
                    labels.append(lab or "(no id)")
                ids.append(rid)

            # Selector + Open button
            cols = st.columns([3, 1])
            with cols[0]:
                choice = st.selectbox(
                    "Pick a child record to open",
                    options=labels,
                    index=0,
                    key=f"child_pick_{child_obj.api_name}_{rel.name}",
                )
            with cols[1]:
                if st.button("Open child", key=f"child_open_{child_obj.api_name}_{rel.name}"):
                    child_id = _id_from_label(choice) or choice
                    if not child_id:
                        st.warning("Selected row has no Id; cannot navigate.")
                    else:
                        push(child_obj.api_name, child_id, label=choice)
                        st.rerun()

            # Show table
            display_cols = select_display_columns(
                child_obj.api_name,
                child_df,
                show_all_fields,
                show_ids=show_ids,
            )
            if display_cols:
                st.dataframe(
                    child_df[display_cols],
                    width="stretch",
                    hide_index=True,
                    height=260,
                )
            else:
                st.dataframe(child_df, width="stretch", hide_index=True, height=260)
