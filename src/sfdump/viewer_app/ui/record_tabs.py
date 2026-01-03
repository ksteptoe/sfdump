from __future__ import annotations

from typing import Any

import streamlit as st

from sfdump.viewer_app.services.display import get_important_fields, select_display_columns


def _child_label(api_name: str, row: dict[str, Any]) -> str:
    """
    Build a stable, readable label: prefer important fields, then Name/Subject/Title,
    always include [Id] so we can reliably parse it back.
    """
    rid = str(row.get("Id", "") or "").strip()

    cols = set(row.keys())
    important = [c for c in get_important_fields(api_name) if c in cols]

    parts: list[str] = []
    for c in important:
        v = str(row.get(c, "") or "").strip()
        if v:
            parts.append(v)

    if not parts:
        for c in ("Name", "Subject", "Title", "DocumentTitle"):
            v = str(row.get(c, "") or "").strip()
            if v:
                parts.append(v)
                break

    label = " — ".join(parts) if parts else rid
    return f"{label} [{rid}]" if rid else label


def _id_from_label(label: str) -> str:
    s = (label or "").strip()
    if s.endswith("]") and "[" in s:
        return s.rsplit("[", 1)[-1].rstrip("]").strip()
    return ""


def render_children_with_navigation(*, record, show_all_fields: bool, show_ids: bool) -> None:
    """
    Children tab renderer WITH explicit navigation controls.

    For each relationship expander:
      - shows a dataframe
      - provides a selectbox to pick a child
      - provides an Open button that pushes onto nav stack and reruns
    """
    if not getattr(record, "children", None):
        st.info("No child records found for this record.")
        return

    st.caption(
        "Tip: open a relationship, pick a child record, then click **Open** to navigate down."
    )

    for coll in record.children:
        child_obj = coll.sf_object
        rel = coll.relationship

        title = (
            f"{child_obj.api_name} via {rel.child_field} "
            f"(relationship: {rel.name}, {len(coll.records)} record(s))"
        )

        with st.expander(title, expanded=False):
            if not coll.records:
                # Provide contextual messages for common scenarios
                msg = "No rows."

                # Check if this is an Opportunity with no Invoices
                if (
                    record.parent.sf_object.api_name == "Opportunity"
                    and child_obj.api_name == "c2g__codaInvoice__c"
                ):
                    stage = record.parent.data.get("StageName", "").strip()
                    if stage in ("Closed Lost", "Closed Won"):
                        if stage == "Closed Lost":
                            msg = (
                                f"ℹ️ No invoices found. This is expected for Closed Lost opportunities "
                                f"(Stage: {stage}), as they typically don't generate invoices."
                            )
                        else:
                            msg = (
                                "ℹ️ No invoices found for this Closed Won opportunity. "
                                "Invoices may not have been created yet, or were created outside of this opportunity."
                            )
                    else:
                        msg = f"ℹ️ No invoices found (Opportunity Stage: {stage})."

                st.info(msg)
                continue

            try:
                import pandas as pd  # type: ignore[import-not-found]
            except Exception:
                st.error("pandas is required to render child tables.")
                return

            child_df = pd.DataFrame(coll.records)
            if child_df.empty:
                st.info("No rows.")
                continue

            display_cols = select_display_columns(
                child_obj.api_name, child_df, show_all_fields, show_ids=show_ids
            )

            st.dataframe(
                child_df[display_cols],
                width="stretch",
                hide_index=True,
                height=260,
            )

            # --- Navigation controls (THE FIX) ---
            # Build choices from records dicts so we always have Id
            choices = [
                _child_label(child_obj.api_name, r)
                for r in coll.records
                if str(r.get("Id", "") or "").strip()
            ]

            if not choices:
                st.info("No Ids available to navigate to in this relationship.")
                continue

            # Keep widget keys stable & unique per relationship
            key_base = f"child_nav_{record.parent.sf_object.api_name}_{record.parent.data.get('Id','')}_{child_obj.api_name}_{rel.name}"

            # Use session state key for the selectbox so we can reliably read it
            select_key = f"{key_base}_select"

            cols = st.columns([4, 1])
            with cols[0]:
                st.selectbox(
                    "Select a child record",
                    options=choices,
                    index=0,
                    key=select_key,
                )

            # Get the selected value from session state (more reliable than variable)
            sel = st.session_state.get(select_key, choices[0] if choices else "")

            # Show what's currently selected (for debugging)
            st.caption(f"Selected: {sel}")

            with cols[1]:
                from sfdump.viewer_app.navigation.record_nav import peek, push

                if st.button("Open", key=f"{key_base}_open"):
                    # Get the CURRENT selection from session state at button click time
                    current_sel = st.session_state.get(select_key, choices[0] if choices else "")

                    # Extract ID and debug
                    rid = _id_from_label(current_sel)
                    label = current_sel.rsplit("[", 1)[0].strip()

                    # Save debug info to session state so we can see it after rerun
                    st.session_state["_debug_last_nav"] = {
                        "select_key": select_key,
                        "current_sel": current_sel,
                        "extracted_id": rid,
                        "label": label,
                        "child_api": child_obj.api_name,
                    }

                    # NAV-002: ensure parent is on nav stack before drilling into child
                    parent_api = record.parent.sf_object.api_name
                    parent_id = str(
                        record.parent.data.get(record.parent.sf_object.id_field, "")
                        or record.parent.data.get("Id", "")
                        or ""
                    )
                    parent_label = str(
                        record.parent.data.get("Name", "")
                        or record.parent.data.get("Subject", "")
                        or record.parent.data.get("Title", "")
                        or parent_id
                    ).strip()

                    cur = peek()
                    if cur is None or cur.api_name != parent_api or cur.record_id != parent_id:
                        push(parent_api, parent_id, label=parent_label)

                    push(child_obj.api_name, rid, label=label)
                    st.rerun()
