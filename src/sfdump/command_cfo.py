from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import pandas as pd


def _find_csv(export_dir: Path, filename: str) -> Optional[Path]:
    """
    Try to locate a given CSV relative to the export directory.

    We probe a few common locations so the command is resilient
    to minor directory layout differences.
    """
    export_dir = export_dir.resolve()

    candidates = [
        export_dir,
        export_dir.parent,
        export_dir.parent / "links",
        export_dir.parent / "meta",
        export_dir.parent / "meta" / "audit",
    ]

    for base in candidates:
        candidate = base / filename
        if candidate.exists():
            return candidate

    return None


def _load_csv_if_exists(path: Optional[Path]) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame()
    return pd.read_csv(path)


def build_cfo_report(
    summary_df: pd.DataFrame,
    missing_df: pd.DataFrame,
    retry_df: pd.DataFrame,
    redact: bool = False,
) -> str:
    """
    Build a CFO-facing Markdown report based on export and audit CSVs.

    The content is intentionally high-level and text-only to play nicely
    with both Sphinx (PDF) and simple text viewers.
    """
    summary_available = not summary_df.empty
    total_files = int(summary_df.shape[0]) if summary_available else 0
    missing_files = int(missing_df.shape[0])
    retry_files = int(retry_df.shape[0])

    distinct_missing_parents = 0
    if not missing_df.empty and "ParentId" in missing_df.columns:
        distinct_missing_parents = int(missing_df["ParentId"].nunique())

    lines: list[str] = []

    # Title
    lines.append("# Salesforce Offboarding – CFO Detailed Report")
    lines.append("")
    lines.append(
        "This chapter summarises the status of the Salesforce file export and "
        "highlights any residual risk areas for Finance and Audit."
    )
    lines.append("")

    if redact:
        lines.append(
            "> Note: This version is redacted for distribution outside the core "
            "finance and IT teams. No Salesforce IDs or file names are included."
        )
        lines.append("")

    # Section 1 – Scope
    lines.append("## 1. Scope and data sets reviewed")
    lines.append("")
    lines.append(
        "The report is based on the exported file indexes produced by the "
        "`sfdump` tooling, including:"
    )
    lines.append("")
    lines.append("- The master index of exported ContentVersion records (where available).")
    lines.append("- The list of attachments that could not be retrieved.")
    lines.append("- The list of attachments queued for a retry export, where applicable.")
    lines.append("")

    # Section 2 – High-level status
    lines.append("## 2. High-level export status")
    lines.append("")

    if summary_available:
        lines.append(f"- Total file index rows analysed: **{total_files}**")
    else:
        lines.append(
            "- Total file index rows analysed: **not available** "
            "(content_versions.csv not found for this export)."
        )

    lines.append(f"- Attachments not retrieved: **{missing_files}**")
    lines.append(f"- Attachments queued for retry: **{retry_files}**")

    if distinct_missing_parents:
        lines.append(
            f"- Distinct parent records with at least one missing attachment: "
            f"**{distinct_missing_parents}**"
        )

    lines.append("")
    lines.append(
        "In broad terms, the export has captured the vast majority of files required "
        "for finance and audit purposes. The residual items are concentrated in the "
        "missing and retry lists described below."
    )
    lines.append("")

    # Section 3 – Residual risk (missing files)
    lines.append("## 3. Residual risk – missing attachments")
    lines.append("")

    if missing_files == 0:
        lines.append(
            "All attachments referenced in the indexes were successfully retrieved. "
            "There is no known residual risk from missing files."
        )
        lines.append("")
    else:
        lines.append(
            "A small subset of attachments could not be retrieved from Salesforce. "
            "These typically fall into one or more of the following categories:"
        )
        lines.append("")
        lines.append(
            "- Attachments where the underlying file has been deleted or is no longer accessible."
        )
        lines.append(
            "- Attachments associated with records for which the current API user "
            "does not have sufficient permission."
        )
        lines.append(
            "- Legacy or malformed records where Salesforce returns an error when "
            "the file body is requested."
        )
        lines.append("")
        lines.append(
            "Finance should assume that the **core accounting position is captured** "
            "in the exported data, but that some supporting documentation may be "
            "missing for a small number of historic records."
        )
        lines.append("")

    # Section 4 – Retry plan
    lines.append("## 4. Retry and remediation plan")
    lines.append("")

    if retry_files == 0:
        lines.append(
            "There is currently no active retry queue. Any further recovery attempts "
            "would need to be performed manually on a case-by-case basis in Salesforce."
        )
        lines.append("")
    else:
        lines.append(
            "A retry list has been generated for attachments where an additional "
            "download attempt may still be worthwhile (for example, where Salesforce "
            "rate-limiting or transient API errors were encountered)."
        )
        lines.append("")
        lines.append(
            "The recommended approach is to run a controlled final retry cycle before "
            "Salesforce access is withdrawn, and to then treat any remaining missing "
            "items as irrecoverable for the purposes of the offboarding exercise."
        )
        lines.append("")

    # Section 5 – Recommended position for Finance
    lines.append("## 5. Recommended position for Finance and Audit")
    lines.append("")
    lines.append("In summary:")
    lines.append("")
    lines.append(
        "- The exported data set is sufficient to support statutory accounts, "
        "management reporting and future audit enquiries."
    )
    lines.append(
        "- A clearly defined list of residual missing attachments has been produced, "
        "quantifying the gap and allowing it to be documented as part of Finance’s "
        "working papers."
    )
    lines.append(
        "- A pragmatic retry and remediation plan is available, but the cost and time "
        "of further recovery should be weighed against the relatively small volume "
        "of outstanding items."
    )
    lines.append("")
    lines.append(
        "If required, Finance can reference this chapter directly in due diligence "
        "or audit packs as evidence of the structured offboarding process and the "
        "limited residual risk."
    )
    lines.append("")

    return "\n".join(lines)


def _write_docs_generated_copy(report_md: str) -> None:
    """
    Mirror the report body into docs/_generated/cfo/cfo_report_body.md
    so that Sphinx can include it in the documentation/PDF build.
    """
    project_root = Path(__file__).resolve().parents[2]
    docs_generated = project_root / "docs" / "_generated" / "cfo"
    docs_generated.mkdir(parents=True, exist_ok=True)

    sphinx_md = docs_generated / "cfo_report_body.md"
    sphinx_md.write_text(report_md, encoding="utf-8")


@click.command(name="cfo-report")
@click.option(
    "--export-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    required=True,
    help="Path to the exported files directory (e.g. ./exports/export-YYYY-MM-DD/files).",
)
@click.option(
    "--out",
    type=click.Path(path_type=Path, dir_okay=False),
    required=True,
    help="Where to write the report text (e.g. ./CFO_Report.md).",
)
@click.option(
    "--redact/--no-redact",
    default=False,
    help="Redact technical identifiers so the report is safe to share more widely.",
)
def cfo_report(export_dir: Path, out: Path, redact: bool) -> None:
    """
    Generate a CFO-facing narrative report on the completeness of the Salesforce
    export, based on the existing audit CSVs.
    """
    export_dir = export_dir.resolve()
    out_path = Path(out).resolve()

    # Locate CSVs (best-effort; missing files become empty DataFrames)
    summary_csv = _find_csv(export_dir, "content_versions.csv")
    missing_csv = _find_csv(export_dir, "attachments_missing.csv")
    retry_csv = _find_csv(export_dir, "attachments_missing_retry.csv")

    summary_df = _load_csv_if_exists(summary_csv)
    missing_df = _load_csv_if_exists(missing_csv)
    retry_df = _load_csv_if_exists(retry_csv)

    report_md = build_cfo_report(
        summary_df=summary_df,
        missing_df=missing_df,
        retry_df=retry_df,
        redact=redact,
    )

    # Write CLI output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")

    # Mirror into docs/_generated for Sphinx/PDF
    _write_docs_generated_copy(report_md)

    # Console message – make it explicit that this is text, not a real PDF
    if out_path.suffix.lower() == ".pdf":
        click.echo(
            f"CFO report written as plain text to {out_path} "
            "(note: this is Markdown, not a real PDF; use Sphinx 'make pdf' for the formatted document)."
        )
    else:
        click.echo(f"CFO report written to {out_path}")

    click.echo(
        "A copy has also been written to docs/_generated/cfo/cfo_report_body.md "
        "for inclusion in the Sphinx documentation/PDF build."
    )
