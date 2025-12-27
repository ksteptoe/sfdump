from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from .nav import nav_back_button, nav_breadcrumb, nav_current, nav_init, nav_open_button


@dataclass(frozen=True)
class Repo:
    export_root: Path
    master_docs: pd.DataFrame
    record_docs: pd.DataFrame
    invoices: Optional[pd.DataFrame]


def _read_csv_if_exists(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    return pd.read_csv(path, dtype=str).fillna("")


def _pick_invoice_csv(meta_dir: Path) -> Optional[Path]:
    # Heuristic: pick a csv with "invoice" in name and an Id-like column.
    candidates = sorted([p for p in meta_dir.glob("*.csv") if "invoice" in p.name.lower()])
    for p in candidates:
        try:
            with p.open("r", encoding="utf-8", errors="replace") as f:
                header = f.readline().strip().lower().split(",")
            if any(h in header for h in ("id", "invoice_id")):
                return p
        except Exception:
            continue
    return candidates[0] if candidates else None


def _best_col(df: pd.DataFrame, *names: str) -> Optional[str]:
    cols = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols:
            return cols[n.lower()]
    return None


@st.cache_data(show_spinner=False)
def load_repo(export_root_str: str) -> Repo:
    export_root = Path(export_root_str).expanduser().resolve()
    meta = export_root / "meta"

    master_path = meta / "master_documents_index.csv"
    record_docs_path = meta / "record_documents.csv"

    master_docs = _read_csv_if_exists(master_path)
    if master_docs is None:
        # Fall back: scan for the master index by filename fragment
        fallback = next(iter(meta.glob("*master*documents*index*.csv")), None)
        if fallback is None:
            raise FileNotFoundError(f"Could not find master_documents_index.csv under {meta}")
        master_docs = pd.read_csv(fallback, dtype=str).fillna("")

    record_docs = _read_csv_if_exists(record_docs_path)
    if record_docs is None:
        fallback = next(iter(meta.glob("*record*documents*.csv")), None)
        if fallback is None:
            # Keep empty but present – app can still browse docs.
            record_docs = pd.DataFrame()
        else:
            record_docs = pd.read_csv(fallback, dtype=str).fillna("")

    invoice_csv = _pick_invoice_csv(meta)
    invoices = _read_csv_if_exists(invoice_csv) if invoice_csv else None

    return Repo(
        export_root=export_root, master_docs=master_docs, record_docs=record_docs, invoices=invoices
    )


def _sidebar_export_root() -> str:
    default = st.session_state.get("_sfdump_export_root") or st.secrets.get(
        "SFDUMP_EXPORT_ROOT", None
    )
    if default is None:
        default = str(Path("exports").resolve())
    val = st.sidebar.text_input("Export root", value=str(default), key="_sfdump_export_root")
    return val


def render_home(repo: Repo) -> None:
    st.subheader("Browse")
    st.caption("Option A drill-down: use Open/Back to navigate.")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### Invoices")
        if repo.invoices is None or repo.invoices.empty:
            st.info(
                "No invoice CSV detected in meta/. (Heuristic looks for *.csv with 'invoice' in the name.)"
            )
        else:
            id_col = _best_col(repo.invoices, "id", "invoice_id")
            name_col = _best_col(
                repo.invoices, "name", "invoice_number", "invoicenumber", "invoice_no"
            )
            show = repo.invoices.copy()
            if id_col is None:
                st.warning("Invoice CSV has no Id column; cannot drill into invoices.")
            else:
                # Keep it light: show first N rows and a filter
                q = st.text_input("Filter (contains)", value="", key="_sfdump_invoice_filter")
                if q:
                    mask = show.astype(str).apply(lambda s: s.str.contains(q, case=False, na=False))
                    show = show[mask.any(axis=1)]

                limit = st.slider(
                    "Rows", min_value=50, max_value=2000, value=200, step=50, key="_sfdump_inv_rows"
                )
                show = show.head(int(limit))

                for i, row in show.iterrows():
                    inv_id = str(row.get(id_col, ""))
                    label = str(row.get(name_col, inv_id)) if name_col else inv_id
                    cols = st.columns([5, 1])
                    cols[0].write(label)
                    with cols[1]:
                        nav_open_button(
                            label="Open",
                            view="invoice",
                            title=f"Invoice {label}",
                            key=f"open_inv_{inv_id}_{i}",
                            invoice_id=inv_id,
                        )

    with col2:
        st.markdown("#### Documents")
        md = repo.master_docs
        # If file_source exists, prefer Files, otherwise show all.
        if "file_source" in md.columns:
            md = md[md["file_source"].astype(str) == "File"]
        qd = st.text_input("Filter documents (contains)", value="", key="_sfdump_doc_filter")
        if qd:
            mask = md.astype(str).apply(lambda s: s.str.contains(qd, case=False, na=False))
            md = md[mask.any(axis=1)]

        # Prefer content_document_id if present; else any id-like column.
        doc_id_col = _best_col(md, "content_document_id", "document_id", "id")
        title_col = _best_col(md, "title", "file_title", "name")
        md = md.head(200)

        if doc_id_col is None:
            st.warning("master_documents_index has no document id column to drill into.")
        else:
            for i, row in md.iterrows():
                doc_id = str(row.get(doc_id_col, ""))
                label = str(row.get(title_col, doc_id)) if title_col else doc_id
                cols = st.columns([5, 1])
                cols[0].write(label)
                with cols[1]:
                    nav_open_button(
                        label="Open",
                        view="document",
                        title=f"Doc {label}",
                        key=f"open_doc_{doc_id}_{i}",
                        doc_id=doc_id,
                    )


def render_invoice(repo: Repo, invoice_id: str) -> None:
    st.subheader(f"Invoice {invoice_id}")

    if repo.invoices is not None and not repo.invoices.empty:
        id_col = _best_col(repo.invoices, "id", "invoice_id")
        if id_col:
            inv = repo.invoices[repo.invoices[id_col].astype(str) == str(invoice_id)]
            if not inv.empty:
                st.markdown("#### Invoice row")
                st.dataframe(inv, use_container_width=True, hide_index=True)

    st.markdown("#### Linked documents")
    rd = repo.record_docs
    if rd is None or rd.empty:
        st.info("record_documents.csv not found; cannot show linked docs.")
        return

    rec_col = _best_col(rd, "record_id", "linked_entity_id", "parent_id")
    doc_col = _best_col(rd, "content_document_id", "document_id", "doc_id")
    if not rec_col or not doc_col:
        st.warning(
            "record_documents.csv missing expected columns; need record_id + content_document_id."
        )
        st.dataframe(rd.head(50), use_container_width=True)
        return

    links = rd[rd[rec_col].astype(str) == str(invoice_id)].copy()
    if links.empty:
        st.info("No linked documents found for this invoice.")
        return

    md = repo.master_docs
    md_doc_col = _best_col(md, "content_document_id", "document_id", "id")
    if md_doc_col:
        links = links.merge(
            md, left_on=doc_col, right_on=md_doc_col, how="left", suffixes=("", "_md")
        )

    title_col = _best_col(links, "title", "file_title", "name")
    local_col = _best_col(links, "local_path")

    for i, row in links.head(500).iterrows():
        doc_id = str(row.get(doc_col, ""))
        title = str(row.get(title_col, doc_id)) if title_col else doc_id
        local_path = str(row.get(local_col, "")) if local_col else ""
        cols = st.columns([6, 2, 1])
        cols[0].write(title)
        cols[1].caption(local_path if local_path else "(missing local_path)")
        with cols[2]:
            nav_open_button(
                label="Open",
                view="document",
                title=f"Doc {title}",
                key=f"open_doc_from_inv_{invoice_id}_{doc_id}_{i}",
                doc_id=doc_id,
            )


def render_document(repo: Repo, doc_id: str) -> None:
    st.subheader(f"Document {doc_id}")

    md = repo.master_docs
    md_doc_col = _best_col(md, "content_document_id", "document_id", "id")
    if md_doc_col is None:
        st.warning("master_documents_index has no doc id column.")
        st.dataframe(md.head(50), use_container_width=True)
        return

    row = md[md[md_doc_col].astype(str) == str(doc_id)]
    if row.empty:
        st.warning("Document not found in master_documents_index.")
        return

    st.markdown("#### Document row")
    st.dataframe(row, use_container_width=True, hide_index=True)

    local_col = _best_col(row, "local_path")
    if local_col:
        rel = str(row.iloc[0].get(local_col, ""))
        if rel:
            abs_path = repo.export_root / rel
            if abs_path.exists():
                st.success(f"Local file exists: {rel}")
                try:
                    data = abs_path.read_bytes()
                    st.download_button(
                        "Download file",
                        data=data,
                        file_name=abs_path.name,
                        mime="application/octet-stream",
                        use_container_width=False,
                    )
                except Exception:
                    st.info("File exists but could not be read for download button.")
            else:
                st.warning(f"local_path set but file missing on disk: {rel}")
        else:
            st.warning("Missing local_path (needs backfill/download).")

    st.markdown("#### Linked from (records)")
    rd = repo.record_docs
    if rd is None or rd.empty:
        st.info("record_documents.csv not found; cannot show parents.")
        return

    rec_col = _best_col(rd, "record_id", "linked_entity_id", "parent_id")
    doc_col = _best_col(rd, "content_document_id", "document_id", "doc_id")
    if not rec_col or not doc_col:
        st.warning(
            "record_documents.csv missing expected columns; need record_id + content_document_id."
        )
        return

    parents = rd[rd[doc_col].astype(str) == str(doc_id)].copy()
    if parents.empty:
        st.info("No parent/linked records found for this document.")
        return

    # If invoices exist, label invoice parents more clearly.
    inv_id_col = None
    inv_name_col = None
    if repo.invoices is not None and not repo.invoices.empty:
        inv_id_col = _best_col(repo.invoices, "id", "invoice_id")
        inv_name_col = _best_col(
            repo.invoices, "name", "invoice_number", "invoicenumber", "invoice_no"
        )

    for i, r in parents.head(500).iterrows():
        rid = str(r.get(rec_col, ""))
        label = rid
        if (
            inv_id_col
            and rid
            and (repo.invoices[repo.invoices[inv_id_col].astype(str) == rid].shape[0] > 0)
        ):
            inv_row = repo.invoices[repo.invoices[inv_id_col].astype(str) == rid].iloc[0]
            label = str(inv_row.get(inv_name_col, rid)) if inv_name_col else rid
            kind = "Invoice"
        else:
            kind = "Record"

        cols = st.columns([6, 1, 1])
        cols[0].write(f"{kind}: {label}")
        if kind == "Invoice":
            with cols[1]:
                nav_open_button(
                    label="Open",
                    view="invoice",
                    title=f"Invoice {label}",
                    key=f"open_inv_from_doc_{rid}_{doc_id}_{i}",
                    invoice_id=rid,
                )


def main() -> None:
    st.set_page_config(page_title="sfdump viewer", layout="wide")

    nav_init()

    export_root = _sidebar_export_root()
    repo = load_repo(export_root)

    st.caption(nav_breadcrumb())
    nav_back_button()

    frame = nav_current()
    if frame.view == "home":
        render_home(repo)
    elif frame.view == "invoice":
        render_invoice(repo, str(frame.params.get("invoice_id", "")))
    elif frame.view == "document":
        render_document(repo, str(frame.params.get("doc_id", "")))
    else:
        st.error(f"Unknown view: {frame.view}")


if __name__ == "__main__":
    main()
