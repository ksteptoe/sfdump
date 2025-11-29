import sys
from pathlib import Path

import pandas as pd


def rebuild_master_index(export_root: Path) -> None:
    export_root = export_root.resolve()
    files_dir = export_root / "files"
    links_dir = files_dir / "links"
    meta_dir = export_root / "meta"
    meta_dir.mkdir(exist_ok=True)

    print(f"Using export_root = {export_root}")

    # --- 1) Load attachment + ContentVersion metadata ------------------------
    att_csv = links_dir / "attachments.csv"
    cv_csv = links_dir / "content_versions.csv"
    cdl_csv = links_dir / "content_document_links.csv"

    print(f"Loading: {att_csv}")
    att = pd.read_csv(att_csv, dtype=str).fillna("") if att_csv.exists() else pd.DataFrame()

    print(f"Loading: {cv_csv}")
    cv = pd.read_csv(cv_csv, dtype=str).fillna("") if cv_csv.exists() else pd.DataFrame()

    print(f"Loading: {cdl_csv}")
    #    cdl = pd.read_csv(cdl_csv, dtype=str).fillna("") if cdl_csv.exists() else pd.DataFrame()

    # Normalise attachment metadata
    if not att.empty:
        att = att.rename(
            columns={
                "Id": "attachment_id",
                "path": "attachment_path",
            }
        )
    else:
        att["attachment_id"] = []
        att["attachment_path"] = []

    # Normalise ContentVersion metadata
    if not cv.empty:
        cv = cv.rename(
            columns={
                "Id": "content_version_id",
                "ContentDocumentId": "content_document_id",
                "path": "content_path",
                "Title": "cv_title",
                "FileType": "cv_filetype",
            }
        )
    else:
        cv["content_document_id"] = []
        cv["content_path"] = []

    # --- 2) Load all per-object *_files_index.csv ---------------------------
    indices = []
    for p in sorted(files_dir.glob("*_files_index.csv")):
        df_i = pd.read_csv(p, dtype=str).fillna("")
        df_i["index_source_file"] = p.name
        indices.append(df_i)

    if not indices:
        raise SystemExit(f"No *_files_index.csv files found under {files_dir}")

    file_index = pd.concat(indices, ignore_index=True)
    print(f"Loaded {len(file_index)} rows from {len(indices)} per-object index files")

    # --- 3) Attach attachment_path for Attachment rows ----------------------
    # Assumption: file_source='Attachment' and file_id=Attachment.Id
    merged = file_index.copy()

    if not att.empty:
        merged = merged.merge(
            att[["attachment_id", "attachment_path"]],
            how="left",
            left_on="file_id",
            right_on="attachment_id",
        )
    else:
        merged["attachment_id"] = ""
        merged["attachment_path"] = ""

    # --- 4) Attach content_document_id + content_path for File rows ---------
    # We assume file_source='File' rows have file_id=ContentDocumentId.
    if not cv.empty:
        merged = merged.merge(
            cv[["content_document_id", "content_path", "content_version_id"]],
            how="left",
            left_on="file_id",
            right_on="content_document_id",
        )
    else:
        merged["content_document_id"] = ""
        merged["content_path"] = ""
        merged["content_version_id"] = ""

    # --- 5) Compute local_path relative to export_root ----------------------
    # attachment_path/content_path are relative to export_root/files
    def compute_local_path(row: pd.Series) -> str:
        # Prefer attachment first, then content file
        if row.get("attachment_path"):
            return f"files/{row['attachment_path']}"
        if row.get("content_path"):
            return f"files/{row['content_path']}"
        return ""

    merged["local_path"] = merged.apply(compute_local_path, axis=1)

    # --- 6) Reorder / select columns into the master index ------------------
    # Use a robust superset based on your previous master index
    preferred_cols = [
        "file_source",
        "file_name",
        "file_extension",
        "local_path",
        "object_type",
        "record_name",
        "record_id",
        "file_id",
        "file_link_id",
        "index_source_file",
        "attachment_id",
        "attachment_path",
        "content_document_id",
        "content_path",
        "content_version_id",
    ]

    cols = [c for c in preferred_cols if c in merged.columns]
    master = merged[cols].copy()

    out_csv = meta_dir / "master_documents_index.csv"
    master.to_csv(out_csv, index=False)
    print(f"Wrote master index: {out_csv} ({len(master)} rows)")

    # --- 7) Sanity print: how many still lack local_path --------------------
    missing = master[
        (master["file_source"].isin(["File", "Attachment"])) & (master["local_path"] == "")
    ]
    print(f"Missing local_path after rebuild: {len(missing)}")
    if not missing.empty:
        print("By file_source:")
        print(missing["file_source"].value_counts())
        print("\nBy object_type (top 10):")
        if "object_type" in missing.columns:
            print(missing["object_type"].value_counts().head(10))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python rebuild_master_index_2025_11_28.py <export_root>")
        print("Example: python rebuild_master_index_2025_11_28.py ./exports/export-2025-11-28")
        raise SystemExit(1)

    rebuild_master_index(Path(sys.argv[1]))
