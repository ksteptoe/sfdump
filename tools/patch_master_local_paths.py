import sys
from pathlib import Path

import pandas as pd


def patch_master_local_paths(export_root: Path) -> None:
    export_root = export_root.resolve()
    meta_dir = export_root / "meta"
    files_dir = export_root / "files"
    links_dir = files_dir / "links"

    master_csv = meta_dir / "master_documents_index.csv"
    cv_csv = links_dir / "content_versions.csv"

    print(f"Export root: {export_root}")
    print(f"Master index: {master_csv}")
    print(f"ContentVersions: {cv_csv}")

    if not master_csv.exists():
        raise SystemExit(f"Master index not found: {master_csv}")
    if not cv_csv.exists():
        raise SystemExit(f"ContentVersions CSV not found: {cv_csv}")

    df = pd.read_csv(master_csv, dtype=str).fillna("")
    print(f"Loaded master index with {len(df)} rows")

    cv = pd.read_csv(cv_csv, dtype=str).fillna("")
    if cv.empty:
        raise SystemExit("content_versions.csv is empty – nothing to patch from.")

    cv = cv.rename(
        columns={
            "Id": "content_version_id",
            "ContentDocumentId": "content_document_id",
            "path": "content_path",
        }
    )

    # Helper: apply patch for a subset with a specific join
    def patch_subset(df: pd.DataFrame, mask: pd.Series, join_on: str, cv_key: str) -> int:
        subset = df[mask].copy()
        print(f"  subset size before {join_on}->{cv_key} patch: {len(subset)}")
        if subset.empty:
            return 0

        subset["__orig_index__"] = subset.index

        patched = subset.merge(
            cv[[cv_key, "content_path"]],
            how="left",
            left_on=join_on,
            right_on=cv_key,
        )

        def compute_local_path(row: pd.Series) -> str:
            if row.get("local_path"):  # already set
                return row["local_path"]
            if row.get("content_path"):
                return f"files/{row['content_path']}"
            return ""

        patched["local_path"] = patched.apply(compute_local_path, axis=1)

        # Only rows where we actually gained a path
        has_path = patched["local_path"] != ""
        updated = patched[has_path]
        print(f"  rows gaining a local_path via {join_on}->{cv_key}: {len(updated)}")

        if updated.empty:
            return 0

        orig_idx = updated["__orig_index__"]
        df.loc[orig_idx, "local_path"] = updated["local_path"]

        # Optionally preserve join keys/paths
        for col in ["content_document_id", "content_path", "content_version_id"]:
            if col in updated.columns:
                if col not in df.columns:
                    df[col] = ""
                df.loc[orig_idx, col] = updated[col]

        return len(updated)

    # Initial count
    base_mask = (df["file_source"] == "File") & (df["local_path"] == "")
    print(f"File rows with empty local_path before patch: {base_mask.sum()}")

    # Pass 1: join on content_document_id -> cv.content_document_id
    if "content_document_id" in df.columns:
        print("Pass 1: joining master.content_document_id -> cv.content_document_id")
        updated_1 = patch_subset(df, base_mask, "content_document_id", "content_document_id")
    else:
        print("Pass 1 skipped: no content_document_id column in master index")
        updated_1 = 0

    # Recompute mask for remaining gaps
    mask_after_1 = (df["file_source"] == "File") & (df["local_path"] == "")
    print(f"After pass 1, remaining File rows with empty local_path: {mask_after_1.sum()}")

    # Pass 2: join on file_id -> cv.content_version_id
    if "file_id" in df.columns:
        print("Pass 2: joining master.file_id -> cv.content_version_id")
        updated_2 = patch_subset(df, mask_after_1, "file_id", "content_version_id")
    else:
        print("Pass 2 skipped: no file_id column in master index")
        updated_2 = 0

    # Final check for File/Attachment missing paths
    df.to_csv(master_csv, index=False)
    print(f"Patched master index written back to: {master_csv}")
    print(f"Total rows gaining local_path: {updated_1 + updated_2}")

    missing = df[(df["file_source"].isin(["File", "Attachment"])) & (df["local_path"] == "")]
    print(f"Missing local_path after patch: {len(missing)}")
    if not missing.empty:
        print("\nStill missing by file_source:")
        print(missing["file_source"].value_counts())
        if "object_type" in missing.columns:
            print("\nStill missing by object_type (top 10):")
            print(missing["object_type"].value_counts().head(10))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python patch_master_local_paths.py <export_root>")
        print("Example: python patch_master_local_paths.py ./exports/export-2025-11-28")
        raise SystemExit(1)

    patch_master_local_paths(Path(sys.argv[1]))
