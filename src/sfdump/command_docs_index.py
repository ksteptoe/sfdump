from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

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


def _pick_path_column(df: "pd.DataFrame", preferred: List[str]) -> Optional[str]:
    """Pick a path-like column from a dataframe.

    We first try exact matches in `preferred`, then fall back to any column
    containing 'path' (case-insensitive).
    """
    for c in preferred:
        if c in df.columns:
            return c

    candidates = [c for c in df.columns if "path" in c.lower()]
    return candidates[0] if candidates else None


def _normalize_export_rel_path(rel_path: object) -> str:
    """Return a path relative to EXPORT_ROOT.

    - If rel_path already starts with 'files/' or 'files_legacy/', keep it.
    - Else prefix with 'files/'.
    """
    if rel_path is None:
        return ""

    s = str(rel_path).strip()
    if not s or s.lower() == "nan":
        return ""

    p = s.replace("\\", "/").lstrip("/")

    # Already export-root relative
    if p.lower().startswith("files/") or p.lower().startswith("files_legacy/"):
        return p

    # Otherwise assume it's relative to files/
    return f"files/{p}"


def _prefer_existing(export_root: Path, rel_path: str) -> str:
    """If the computed rel_path doesn't exist but a known legacy variant does, use it.

    This protects older exports where ContentVersion files ended up under:
      EXPORT_ROOT/files/files/<bucket>/...
    """
    if not rel_path:
        return ""

    p = rel_path.replace("\\", "/")
    if (export_root / p).exists():
        return p

    # legacy double-files layout
    if p.lower().startswith("files/") and not p.lower().startswith("files/files/"):
        alt = "files/" + p  # -> files/files/...
        if (export_root / alt).exists():
            return alt

    return p


def _build_master_index(export_root: Path) -> Path:
    """Build meta/master_documents_index.csv for a given export root.

    export_root is expected to contain:
      - csv/
      - links/   (with *_files_index.csv, attachments.csv, content_versions.csv)
      - meta/    (we'll create if missing)
    """
    links_dir = export_root / "links"
    csv_dir = export_root / "csv"
    meta_dir = export_root / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    if not links_dir.exists():
        raise click.ClickException(
            f"Expected links directory not found: {links_dir} "
            "(did you run `sfdump files --out EXPORT_ROOT --index-by ...` ?)"
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
        "Loaded %d document-links from %d index file(s) (links layout: links/).",
        len(index_df),
        len(index_files),
    )

    # ------------------------------------------------------------------
    # 2) Load attachments + content metadata (for local paths)
    # ------------------------------------------------------------------
    attachments_meta = _load_csv(links_dir / ATTACHMENTS_META_FILENAME)
    content_meta = _load_csv(links_dir / CONTENT_META_FILENAME)

    # ---------------- Attachments: normalise id + path -----------------
    # We prefer 'local_path' if present (already export-root relative).
    if not attachments_meta.empty:
        if "Id" not in attachments_meta.columns:
            raise click.ClickException(
                f"Expected column 'Id' in {ATTACHMENTS_META_FILENAME}, found: "
                f"{list(attachments_meta.columns)}"
            )

        attachments_meta = attachments_meta.rename(columns={"Id": "attachment_id"})

        path_col = _pick_path_column(attachments_meta, preferred=["local_path", "path"])
        if path_col:
            attachments_meta = attachments_meta.rename(columns={path_col: "attachment_path"})
        else:
            _logger.warning(
                "No path-like column found in %s; attachment rows will have empty local_path.",
                ATTACHMENTS_META_FILENAME,
            )
            attachments_meta["attachment_path"] = ""

    # --------------- ContentVersion: normalise doc id + path ------------
    if not content_meta.empty:
        rename_map: Dict[str, str] = {}
        if "ContentDocumentId" in content_meta.columns:
            rename_map["ContentDocumentId"] = "content_document_id"
        if "Id" in content_meta.columns:
            rename_map["Id"] = "content_version_id"

        if "content_document_id" not in rename_map.values():
            # docs-index joins on ContentDocumentId, so that must be present
            raise click.ClickException(
                f"Expected 'ContentDocumentId' in {CONTENT_META_FILENAME}, found: "
                f"{list(content_meta.columns)}"
            )

        content_meta = content_meta.rename(columns=rename_map)

        path_col = _pick_path_column(content_meta, preferred=["local_path", "path"])
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
    df_other = index_df[~index_df["file_source"].isin(["Attachment", "File"])].copy()

    # 3a) Attachments: join on file_id == attachment_id
    if not attachments_meta.empty and not df_att.empty:
        df_att = df_att.merge(
            attachments_meta[["attachment_id", "attachment_path"]],
            left_on="file_id",
            right_on="attachment_id",
            how="left",
        )

        # TRUST attachment_path if it is already a local_path (tests use this),
        # otherwise normalise it to export-root relative.
        df_att["local_path"] = df_att["attachment_path"].map(_normalize_export_rel_path)
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
        df_file["local_path"] = df_file["content_path"].map(_normalize_export_rel_path)
    else:
        df_file["local_path"] = ""

    # 3c) Other sources (e.g. InvoicePDF): path is already in the files_index row
    if not df_other.empty:
        df_other["local_path"] = df_other.get("path", pd.Series("", index=df_other.index)).fillna(
            ""
        )
    else:
        df_other["local_path"] = ""

    master = pd.concat([df_att, df_file, df_other], ignore_index=True)
    master["local_path"] = (
        master["local_path"].fillna("").map(lambda p: _prefer_existing(export_root, p))
    )

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
            "AccountId": "opp_account_id",
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
                "Opportunity.csv has none of the expected columns; skipping enrichment (columns: %s)",
                list(opps.columns),
            )

    # --- Accounts: bring name (and join via opp_account_id if present) ---
    if not accounts.empty:
        acct_cols_map = {"Id": "account_id", "Name": "account_name"}
        present_acct_map = {
            src: dst for src, dst in acct_cols_map.items() if src in accounts.columns
        }

        if present_acct_map:
            acct_subset = (
                accounts[list(present_acct_map.keys())].copy().rename(columns=present_acct_map)
            )

            # Direct Account entries
            is_acct = master["object_type"] == "Account"
            if is_acct.any():
                master_acct = master[is_acct].merge(
                    acct_subset,
                    left_on="record_id",
                    right_on="account_id",
                    how="left",
                )
                master = pd.concat([master[~is_acct], master_acct], ignore_index=True)

            # Fill Account via Opportunity's AccountId if present
            if "opp_account_id" in master.columns and "account_id" in acct_subset.columns:
                master = master.merge(
                    acct_subset[["account_id", "account_name"]],
                    left_on="opp_account_id",
                    right_on="account_id",
                    how="left",
                    suffixes=("", "_from_opp"),
                )

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
                        master["account_id"] != "",
                        master["account_id_from_opp"],
                    )
                    master = master.drop(columns=["account_id_from_opp"])

                if "account_name_from_opp" in master.columns:
                    master["account_name"] = master["account_name"].where(
                        master["account_name"] != "",
                        master["account_name_from_opp"],
                    )
                    master = master.drop(columns=["account_name_from_opp"])
        else:
            _logger.warning(
                "Account.csv has none of the expected columns; skipping enrichment (columns: %s)",
                list(accounts.columns),
            )

    # --- Invoices: enrich with Opportunity + Account via FK columns ----
    is_invoice = master["object_type"] == "c2g__codaInvoice__c"
    if is_invoice.any():
        invoice_csv = csv_dir / "c2g__codaInvoice__c.csv"
        inv_meta = _load_csv(invoice_csv)
        if not inv_meta.empty:
            inv_cols = ["Id"]
            inv_rename: Dict[str, str] = {"Id": "inv_id"}
            if "c2g__Opportunity__c" in inv_meta.columns:
                inv_cols.append("c2g__Opportunity__c")
                inv_rename["c2g__Opportunity__c"] = "inv_opp_id"
            if "c2g__Account__c" in inv_meta.columns:
                inv_cols.append("c2g__Account__c")
                inv_rename["c2g__Account__c"] = "inv_acct_id"

            inv_subset = inv_meta[inv_cols].copy().rename(columns=inv_rename)

            master_inv = master[is_invoice].merge(
                inv_subset, left_on="record_id", right_on="inv_id", how="left"
            )

            # Bring Opportunity name via inv_opp_id
            if "inv_opp_id" in master_inv.columns and not opps.empty:
                opp_names = (
                    opps[["Id", "Name"]]
                    .copy()
                    .rename(columns={"Id": "_opp_id", "Name": "_opp_name"})
                )
                if "AccountId" in opps.columns:
                    opp_names["_opp_acct_id"] = opps["AccountId"]
                master_inv = master_inv.merge(
                    opp_names, left_on="inv_opp_id", right_on="_opp_id", how="left"
                )
                if "opp_name" not in master_inv.columns:
                    master_inv["opp_name"] = ""
                master_inv["opp_name"] = master_inv["opp_name"].fillna("")
                master_inv["opp_name"] = master_inv["opp_name"].where(
                    master_inv["opp_name"] != "",
                    master_inv.get("_opp_name", "").fillna("")
                    if "_opp_name" in master_inv.columns
                    else "",
                )

            # Bring Account name via inv_acct_id (or via Opportunity's AccountId)
            if not accounts.empty:
                acct_names = (
                    accounts[["Id", "Name"]]
                    .copy()
                    .rename(columns={"Id": "_acct_id", "Name": "_acct_name"})
                )

                # Try direct account FK first
                acct_id_col = None
                if "inv_acct_id" in master_inv.columns:
                    acct_id_col = "inv_acct_id"
                elif "_opp_acct_id" in master_inv.columns:
                    acct_id_col = "_opp_acct_id"

                if acct_id_col:
                    master_inv = master_inv.merge(
                        acct_names, left_on=acct_id_col, right_on="_acct_id", how="left"
                    )
                    if "account_name" not in master_inv.columns:
                        master_inv["account_name"] = ""
                    master_inv["account_name"] = master_inv["account_name"].fillna("")
                    master_inv["account_name"] = master_inv["account_name"].where(
                        master_inv["account_name"] != "",
                        master_inv.get("_acct_name", "").fillna("")
                        if "_acct_name" in master_inv.columns
                        else "",
                    )

            # Drop temp columns
            drop_cols = [
                c
                for c in master_inv.columns
                if c.startswith("inv_") or c.startswith("_opp_") or c.startswith("_acct_")
            ]
            master_inv = master_inv.drop(columns=drop_cols, errors="ignore")

            master = pd.concat([master[~is_invoice], master_inv], ignore_index=True)

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

    # ------------------------------------------------------------------
    # 6) Validate: check for documents without local files
    # ------------------------------------------------------------------
    total_docs = len(master)
    docs_with_path = len(master[master["local_path"].str.strip() != ""])
    docs_missing_path = total_docs - docs_with_path

    if docs_missing_path > 0:
        missing_pct = (docs_missing_path / total_docs) * 100 if total_docs > 0 else 0
        _logger.info(
            "Master index: %d/%d documents (%.1f%%) pending download",
            docs_missing_path,
            total_docs,
            missing_pct,
        )

    _logger.info("Master documents index written to %s (%d rows).", out_path, len(master))
    return out_path, docs_with_path, docs_missing_path


@click.command("docs-index")
@click.option(
    "--export-root",
    "export_root",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Export root directory (contains csv/, links/, meta/).",
)
def docs_index_cmd(export_root: Path) -> None:
    """Build master_documents_index.csv for a given export root."""
    export_root = export_root.resolve()
    if not export_root.exists():
        raise click.ClickException(f"EXPORT_ROOT does not exist: {export_root}")

    click.echo(f"Building master documents index under: {export_root}")
    out_path, docs_with_path, docs_missing_path = _build_master_index(export_root)
    click.echo(f"Master documents index written to: {out_path}")

    if docs_missing_path > 0:
        total = docs_with_path + docs_missing_path
        click.echo(f"Note: {docs_missing_path}/{total} documents pending download")
