# src/sfdump/command_docs_index.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import click

_logger = logging.getLogger(__name__)

try:
    import pandas as pd
except ImportError as e:  # pragma: no cover - defensive
    raise RuntimeError(
        "pandas is required for `sfdump docs-index`. Install pandas into your environment."
    ) from e

# Filenames – adjust if your actual CSV names differ
ATTACHMENTS_META_FILENAME = "attachments.csv"
CONTENT_META_FILENAME = "content_versions.csv"

ATTACHMENTS_ID_COL = "Id"
ATTACHMENTS_PATH_COL = "path"  # if missing, we'll auto-detect a *path* column

CONTENT_ID_COL = "Id"  # ContentVersion.Id
CONTENT_DOC_ID_COL = "ContentDocumentId"
CONTENT_PATH_COL = "path"  # if missing, we'll auto-detect a *path* column

ACCOUNT_FILENAME = "Account.csv"
OPPORTUNITY_FILENAME = "Opportunity.csv"


def _load_csv(path: Path) -> "pd.DataFrame":
    """Load a CSV with all columns as string, empty DF if missing or empty."""
    if not path.exists():
        _logger.info("Skipping missing CSV: %s", path)
        return pd.DataFrame()

    _logger.debug("Loading CSV: %s", path)
    try:
        return pd.read_csv(path, dtype=str).fillna("")
    except pd.errors.EmptyDataError:
        _logger.info("CSV is empty, treating as no rows: %s", path)
        return pd.DataFrame()


def _norm_rel_path(rel_path: object) -> str:
    """Normalise a stored path into a clean posix-style relative path."""
    if rel_path is None:
        return ""
    s = str(rel_path).strip()
    if not s or s.lower() == "nan":
        return ""
    return s.replace("\\", "/").lstrip("/")


def _find_links_dir(export_root: Path) -> Tuple[Path, str]:
    """Find the directory containing *_files_index.csv and file metadata CSVs.

    Supported layouts:
      - EXPORT_ROOT/files/links
      - EXPORT_ROOT/links
    """
    cand1 = export_root / "files" / "links"
    if cand1.exists():
        return cand1, "files/links"
    cand2 = export_root / "links"
    if cand2.exists():
        return cand2, "links"
    # Default for error message
    return cand1, "files/links"


def _first_existing(export_root: Path, candidates: List[str]) -> Optional[str]:
    """Return the first candidate that exists under export_root."""
    for c in candidates:
        if not c:
            continue
        if (export_root / c).exists():
            return c
    return None


def _resolve_local_path(export_root: Path, rel_path: object, kind: str) -> str:
    """Resolve a local path relative to EXPORT_ROOT by probing common layouts.

    This avoids hard-coded assumptions like 'files/files' by checking what exists.
    Returns a path relative to EXPORT_ROOT.
    """
    p = _norm_rel_path(rel_path)
    if not p:
        return ""

    # If p already looks rooted (files/... or files_legacy/...), keep it as a candidate.
    candidates: List[str] = []

    def add(x: str) -> None:
        x = x.replace("\\", "/").lstrip("/")
        if x and x not in candidates:
            candidates.append(x)

    add(p)

    if kind == "attachment":
        # Attachments typically live under files_legacy/
        if p.lower().startswith("files_legacy/"):
            tail = p[len("files_legacy/") :]
            add(p)  # as-is
            add(f"files/files_legacy/{tail}")  # legacy nested layout
        else:
            add(f"files_legacy/{p}")
            add(f"files/files_legacy/{p}")

        # Some historical exports may have prefixed with files/
        add(f"files/{p}")
        add(f"files/files/{p}")

        preferred = f"files_legacy/{p}" if not p.lower().startswith("files_legacy/") else p
    else:
        # Content files typically live under files/<bucket>/...
        if p.lower().startswith("files/files/"):
            add(p)
            preferred = p
        elif p.lower().startswith("files/"):
            tail = p[len("files/") :]
            add(p)
            add(f"files/files/{tail}")  # legacy nested layout
            preferred = p
        else:
            add(f"files/{p}")
            add(f"files/files/{p}")  # legacy nested layout
            preferred = f"files/{p}"

    found = _first_existing(export_root, candidates)
    return found if found is not None else preferred


def _build_master_index(export_root: Path) -> Path:
    """Build meta/master_documents_index.csv for a given export root.

    export_root is expected to contain:
      - csv/
      - (files/links/ OR links/) with *_files_index.csv and attachments/content meta
      - meta/ (we'll create if missing)
    """
    links_dir, links_layout = _find_links_dir(export_root)
    csv_dir = export_root / "csv"
    meta_dir = export_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    if not links_dir.exists():
        raise click.ClickException(
            f"Expected links directory not found: {links_dir} "
            "(did you run `sfdump files` with --index-by ?)"
        )

    out_path = meta_dir / "master_documents_index.csv"

    # ------------------------------------------------------------------
    # 1) Load all per-object file indexes
    # ------------------------------------------------------------------
    index_files: List[Path] = sorted(links_dir.glob("*_files_index.csv"))
    if not index_files:
        raise click.ClickException(
            f"No *_files_index.csv files found under {links_dir} (nothing to index)."
        )

    dfs = []
    for p in index_files:
        df = _load_csv(p)
        if not df.empty:
            df["index_source_file"] = p.name
            dfs.append(df)

    index_df = pd.concat(dfs, ignore_index=True)
    _logger.info(
        "Loaded %d document-links from %d index file(s) (links layout: %s).",
        len(index_df),
        len(index_files),
        links_layout,
    )

    # ------------------------------------------------------------------
    # 2) Load attachments + content metadata (for local paths)
    # ------------------------------------------------------------------
    attachments_meta = _load_csv(links_dir / ATTACHMENTS_META_FILENAME)
    content_meta = _load_csv(links_dir / CONTENT_META_FILENAME)

    # ---------------- Attachments: normalise id + path -----------------
    if not attachments_meta.empty:
        if ATTACHMENTS_ID_COL not in attachments_meta.columns:
            raise click.ClickException(
                f"Expected column {ATTACHMENTS_ID_COL!r} in "
                f"{ATTACHMENTS_META_FILENAME}, found: "
                f"{list(attachments_meta.columns)}"
            )

        attachments_meta = attachments_meta.rename(columns={ATTACHMENTS_ID_COL: "attachment_id"})

        path_col = (
            ATTACHMENTS_PATH_COL if ATTACHMENTS_PATH_COL in attachments_meta.columns else None
        )
        if path_col is None:
            candidates = [c for c in attachments_meta.columns if "path" in c.lower()]
            if candidates:
                path_col = candidates[0]

        if path_col:
            attachments_meta = attachments_meta.rename(columns={path_col: "attachment_path"})
        else:
            _logger.warning(
                "No path-like column found in %s; attachment rows will have empty local_path.",
                ATTACHMENTS_META_FILENAME,
            )
            attachments_meta["attachment_path"] = ""

    # --------------- ContentVersion: normalise id + path ----------------
    if not content_meta.empty:
        rename_map: Dict[str, str] = {}
        if CONTENT_ID_COL in content_meta.columns:
            rename_map[CONTENT_ID_COL] = "content_version_id"
        if CONTENT_DOC_ID_COL in content_meta.columns:
            rename_map[CONTENT_DOC_ID_COL] = "content_document_id"

        if not rename_map:
            raise click.ClickException(
                f"Expected at least {CONTENT_ID_COL!r} or {CONTENT_DOC_ID_COL!r} "
                f"in {CONTENT_META_FILENAME}, found: "
                f"{list(content_meta.columns)}"
            )

        content_meta = content_meta.rename(columns=rename_map)

        path_col = CONTENT_PATH_COL if CONTENT_PATH_COL in content_meta.columns else None
        if path_col is None:
            candidates = [c for c in content_meta.columns if "path" in c.lower()]
            if candidates:
                path_col = candidates[0]

        if path_col:
            content_meta = content_meta.rename(columns={path_col: "content_path"})
        else:
            _logger.warning(
                "No path-like column found in %s; file rows will have empty local_path.",
                CONTENT_META_FILENAME,
            )
            content_meta["content_path"] = ""

    # ------------------------------------------------------------------
    # 3) Split index by file_source and join metadata
    # ------------------------------------------------------------------
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
        df_att["local_path"] = df_att["attachment_path"].map(
            lambda x: _resolve_local_path(export_root, x, "attachment")
        )
    else:
        df_att["local_path"] = ""

    # 3b) Files (ContentDocument): join via ContentDocumentId
    if not content_meta.empty and not df_file.empty:
        df_file = df_file.merge(
            content_meta[["content_document_id", "content_path"]],
            left_on="file_id",
            right_on="content_document_id",
            how="left",
        )
        df_file["local_path"] = df_file["content_path"].map(
            lambda x: _resolve_local_path(export_root, x, "content")
        )
    else:
        df_file["local_path"] = ""

    master = pd.concat([df_att, df_file], ignore_index=True)
    master["local_path"] = master["local_path"].fillna("")

    # ------------------------------------------------------------------
    # 4) Enrich with basic CRM context (Account & Opportunity)
    # ------------------------------------------------------------------
    accounts = _load_csv(csv_dir / ACCOUNT_FILENAME)
    opps = _load_csv(csv_dir / OPPORTUNITY_FILENAME)

    # --- Opportunities: bring key fields where available ----------------
    if not opps.empty:
        opp_cols_map = {
            "Id": "opp_id",
            "Name": "opp_name",
            "StageName": "opp_stage",
            "Amount": "opp_amount",
            "CloseDate": "opp_close_date",
            "AccountId": "opp_account_id",  # optional; may not exist
        }
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
                master = pd.concat([master[~is_opp], master_opp], ignore_index=True)
        else:
            _logger.warning(
                "Opportunity.csv has none of the expected columns; skipping Opportunity enrichment (columns: %s)",
                list(opps.columns),
            )

    # --- Accounts: bring name (and join from opp_account_id if present) --
    if not accounts.empty:
        acct_cols_map = {"Id": "account_id", "Name": "account_name"}
        present_acct_map = {
            src: dst for src, dst in acct_cols_map.items() if src in accounts.columns
        }

        if present_acct_map:
            acct_subset = accounts[list(present_acct_map.keys())].copy()
            acct_subset = acct_subset.rename(columns=present_acct_map)

            # 1) Direct Account entries (files attached to Account)
            is_acct = master["object_type"] == "Account"
            if is_acct.any():
                master_acct = master[is_acct].merge(
                    acct_subset,
                    left_on="record_id",
                    right_on="account_id",
                    how="left",
                )
                master = pd.concat([master[~is_acct], master_acct], ignore_index=True)

            # 2) Join Account via opp_account_id if present
            if "opp_account_id" in master.columns and "account_id" in acct_subset.columns:
                master = master.merge(
                    acct_subset[["account_id", "account_name"]],
                    left_on="opp_account_id",
                    right_on="account_id",
                    how="left",
                    suffixes=("", "_from_opp"),
                )

                if "account_id" not in master.columns:
                    master["account_id"] = ""
                if "account_name" not in master.columns:
                    master["account_name"] = ""

                for col in [
                    "account_id",
                    "account_name",
                    "account_id_from_opp",
                    "account_name_from_opp",
                ]:
                    if col in master.columns:
                        master[col] = master[col].fillna("")

                if "account_id_from_opp" in master.columns:
                    master["account_id"] = master["account_id"].where(
                        master["account_id"] != "", master["account_id_from_opp"]
                    )
                    master = master.drop(columns=["account_id_from_opp"])

                if "account_name_from_opp" in master.columns:
                    master["account_name"] = master["account_name"].where(
                        master["account_name"] != "", master["account_name_from_opp"]
                    )
                    master = master.drop(columns=["account_name_from_opp"])
        else:
            _logger.warning(
                "Account.csv has none of the expected columns; skipping Account enrichment (columns: %s)",
                list(accounts.columns),
            )

    # ------------------------------------------------------------------
    # 5) Final tidy + write
    # ------------------------------------------------------------------
    key_cols = [
        "file_source",
        "file_name",
        "file_extension",
        "local_path",
        "object_type",
        "record_name",
        "record_id",
        "account_id",
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

    _logger.info("Master documents index written to %s (%d rows).", out_path, len(master))
    return out_path


@click.command("docs-index")
@click.option(
    "--export-root",
    "export_root",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Export root directory (contains csv/, files/, meta/).",
)
def docs_index_cmd(export_root: Path) -> None:
    """Build master_documents_index.csv for a given export root.

    Reads per-object *_files_index.csv and file metadata from either:
      - files/links/ under EXPORT_ROOT, or
      - links/ under EXPORT_ROOT (older layout)

    Enriches with Account and Opportunity context and writes:
      meta/master_documents_index.csv
    """
    export_root = export_root.resolve()
    if not export_root.exists():
        raise click.ClickException(f"EXPORT_ROOT does not exist: {export_root}")

    click.echo(f"Building master documents index under: {export_root}")
    out_path = _build_master_index(export_root)
    click.echo(f"Master documents index written to: {out_path}")
