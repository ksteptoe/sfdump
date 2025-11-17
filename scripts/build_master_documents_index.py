#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# --- Config: adjust these if your CSV names/columns differ -------------------

ATTACHMENTS_META_FILENAME = "attachments.csv"
CONTENT_META_FILENAME = "content_versions.csv"

ATTACHMENTS_ID_COL = "Id"
ATTACHMENTS_PATH_COL = "path"

CONTENT_ID_COL = "Id"  # ContentVersion.Id
CONTENT_DOC_ID_COL = "ContentDocumentId"
CONTENT_PATH_COL = "path"

ACCOUNT_FILENAME = "Account.csv"
OPPORTUNITY_FILENAME = "Opportunity.csv"


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV with all columns as string, empty if missing."""
    if not path.exists():
        print(f"[INFO] Skipping missing CSV: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def build_master_index(export_root: Path) -> Path:
    files_dir = export_root / "files"
    links_dir = files_dir / "links"
    csv_dir = export_root / "csv"
    meta_dir = export_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    out_path = meta_dir / "master_documents_index.csv"

    # 1) Load all per-object file indexes
    index_files = sorted(links_dir.glob("*_files_index.csv"))
    if not index_files:
        raise SystemExit(f"No *_files_index.csv files found under {links_dir}")

    dfs = []
    for p in index_files:
        df = load_csv(p)
        if not df.empty:
            df["index_source_file"] = p.name
            dfs.append(df)

    index_df = pd.concat(dfs, ignore_index=True)
    print(f"[INFO] Loaded {len(index_df):,} document-links from {len(index_files)} index file(s).")

    # 2) Load attachments + content metadata (for local paths)
    attachments_meta = load_csv(links_dir / ATTACHMENTS_META_FILENAME)
    content_meta = load_csv(links_dir / CONTENT_META_FILENAME)

    # ---------------- Attachments: normalise id + path -------------------
    if not attachments_meta.empty:
        # Ensure we have an attachment_id column mapped from ATTACHMENTS_ID_COL
        if ATTACHMENTS_ID_COL not in attachments_meta.columns:
            raise SystemExit(
                f"Expected column {ATTACHMENTS_ID_COL!r} in {ATTACHMENTS_META_FILENAME}, "
                f"found columns: {list(attachments_meta.columns)}"
            )

        attachments_meta = attachments_meta.rename(columns={ATTACHMENTS_ID_COL: "attachment_id"})

        # Try to guess the path column if ATTACHMENTS_PATH_COL is not present
        path_col = None
        # If you've set ATTACHMENTS_PATH_COL to something real, prefer that
        if ATTACHMENTS_PATH_COL in attachments_meta.columns:
            path_col = ATTACHMENTS_PATH_COL
        else:
            # Heuristics: pick the first column whose name contains "path"
            candidates = [c for c in attachments_meta.columns if "path" in c.lower()]
            if candidates:
                path_col = candidates[0]

        if path_col:
            attachments_meta = attachments_meta.rename(columns={path_col: "attachment_path"})
        else:
            # No usable path column; we can still build an index without local_path
            print(
                f"[WARN] No path-like column found in {ATTACHMENTS_META_FILENAME}; "
                "attachment rows will have empty local_path."
            )
            attachments_meta["attachment_path"] = ""

    # ---------------- ContentVersion: normalise id + path ----------------
    if not content_meta.empty:
        # ContentVersion.Id / ContentDocumentId
        rename_map = {}
        if CONTENT_ID_COL in content_meta.columns:
            rename_map[CONTENT_ID_COL] = "content_version_id"
        if CONTENT_DOC_ID_COL in content_meta.columns:
            rename_map[CONTENT_DOC_ID_COL] = "content_document_id"

        if not rename_map:
            raise SystemExit(
                f"Expected at least {CONTENT_ID_COL!r} or {CONTENT_DOC_ID_COL!r} "
                f"in {CONTENT_META_FILENAME}, found: {list(content_meta.columns)}"
            )

        content_meta = content_meta.rename(columns=rename_map)

        # Guess a path column
        path_col = None
        if CONTENT_PATH_COL in content_meta.columns:
            path_col = CONTENT_PATH_COL
        else:
            candidates = [c for c in content_meta.columns if "path" in c.lower()]
            if candidates:
                path_col = candidates[0]

        if path_col:
            content_meta = content_meta.rename(columns={path_col: "content_path"})
        else:
            print(
                f"[WARN] No path-like column found in {CONTENT_META_FILENAME}; "
                "file rows will have empty local_path."
            )
            content_meta["content_path"] = ""

    # 3) Split index by file_source to merge different metadata
    df_att = index_df[index_df["file_source"] == "Attachment"].copy()
    df_file = index_df[index_df["file_source"] == "File"].copy()

    # 3a) Attachments: join on file_id == attachment_id
    if not attachments_meta.empty and not df_att.empty:
        df_att = df_att.merge(
            attachments_meta[["attachment_id", "attachment_path"]],
            left_on="file_id",
            right_on="attachment_id",
            how="left",
        )
        df_att["local_path"] = df_att["attachment_path"]
    else:
        df_att["local_path"] = ""

    # 3b) Files (ContentDocument): join via ContentDocumentId if available
    if not content_meta.empty and not df_file.empty:
        df_file = df_file.merge(
            content_meta[["content_document_id", "content_path"]],
            left_on="file_id",
            right_on="content_document_id",
            how="left",
        )
        df_file["local_path"] = df_file["content_path"]
    else:
        df_file["local_path"] = ""

    # Recombine
    master = pd.concat([df_att, df_file], ignore_index=True)
    master["local_path"] = master["local_path"].fillna("")

    # 4) Enrich with basic CRM context (Account & Opportunity)
    accounts = load_csv(csv_dir / ACCOUNT_FILENAME)
    opps = load_csv(csv_dir / OPPORTUNITY_FILENAME)

    # --- Opportunities: bring key fields where available -----------------
    if not opps.empty:
        opp_cols_map = {
            "Id": "opp_id",
            "Name": "opp_name",
            "StageName": "opp_stage",
            "Amount": "opp_amount",
            "CloseDate": "opp_close_date",
            "AccountId": "opp_account_id",  # optional; may not exist
        }
        # Keep only columns that actually exist in Opportunity.csv
        present_map = {src: dst for src, dst in opp_cols_map.items() if src in opps.columns}

        if present_map:
            opps_subset = opps[list(present_map.keys())].copy()
            opps_subset = opps_subset.rename(columns=present_map)

            is_opp = master["object_type"] == "Opportunity"
            if is_opp.any():
                master_opp = master[is_opp].merge(
                    opps_subset,
                    left_on="record_id",
                    right_on="opp_id",
                    how="left",
                )
                master = pd.concat(
                    [master[~is_opp], master_opp],
                    ignore_index=True,
                )
        else:
            print(
                "[WARN] Opportunity.csv has none of the expected columns "
                f"(found: {list(opps.columns)}); skipping Opportunity enrichment."
            )

    # --- Accounts: bring name (and link from opp_account_id if present) --
    if not accounts.empty:
        acct_cols_map = {
            "Id": "account_id",
            "Name": "account_name",
        }
        present_acct_map = {
            src: dst for src, dst in acct_cols_map.items() if src in accounts.columns
        }

        if present_acct_map:
            acct_subset = accounts[list(present_acct_map.keys())].copy()
            acct_subset = acct_subset.rename(columns=present_acct_map)

            # 1) Direct Account entries in master
            is_acct = master["object_type"] == "Account"
            if is_acct.any():
                master_acct = master[is_acct].merge(
                    acct_subset,
                    left_on="record_id",
                    right_on="account_id",
                    how="left",
                )
                master = pd.concat(
                    [master[~is_acct], master_acct],
                    ignore_index=True,
                )

            # 2) If we have opp_account_id (from opportunity enrichment), join again
            if "opp_account_id" in master.columns and "account_id" in acct_subset.columns:
                master = master.merge(
                    acct_subset[["account_id", "account_name"]],
                    left_on="opp_account_id",
                    right_on="account_id",
                    how="left",
                    suffixes=("", "_from_opp"),
                )
        else:
            print(
                "[WARN] Account.csv has none of the expected columns "
                f"(found: {list(accounts.columns)}); skipping Account enrichment."
            )

    # 5) Final tidy + write
    # Reorder some key columns to the front
    key_cols = [
        "file_source",
        "file_name",
        "file_extension",
        "local_path",
        "object_type",
        "record_name",
        "record_id",
        "account_name",
        "opp_name",
        "opp_stage",
        "opp_amount",
        "opp_close_date",
    ]
    key_cols = [c for c in key_cols if c in master.columns]

    other_cols = [c for c in master.columns if c not in key_cols]
    master = master[key_cols + other_cols]

    master.to_csv(out_path, index=False)
    print(f"[INFO] Master documents index written to: {out_path} ({len(master):,} rows)")
    return out_path


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        print("Usage: python build_master_documents_index.py EXPORT_ROOT")
        print("Example: python build_master_documents_index.py ./exports/export-2025-11-15")
        raise SystemExit(1)

    export_root = Path(argv[1]).resolve()
    if not export_root.exists():
        raise SystemExit(f"EXPORT_ROOT does not exist: {export_root}")

    build_master_index(export_root)


if __name__ == "__main__":
    main(sys.argv)
