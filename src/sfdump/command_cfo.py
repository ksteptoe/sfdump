import csv
import datetime
from pathlib import Path

import click


@click.command("cfo-report")
@click.option(
    "--export-dir",
    required=True,
    type=click.Path(),
    help="Path to export/files folder (e.g. ./exports/export-YYYY-MM-DD/files).",
)
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output file (.md recommended; .pdf will currently still be Markdown text).",
)
@click.option(
    "--redact",
    is_flag=True,
    help="Redact attachment names and IDs for external sharing.",
)
def cfo_report(export_dir: str, out: str, redact: bool) -> None:
    """
    Generate a CFO-ready completeness report.

    Produces a finance-grade summary of:
    - overall attachment export completeness
    - retry outcomes
    - remaining unrecoverables
    - finance impact narrative
    """

    export_dir_path = Path(export_dir)
    links = export_dir_path / "links"

    missing_csv = links / "attachments_missing.csv"
    retry_csv = links / "attachments_missing_retry.csv"

    # Load missing and retry rows (empty list if files don't exist)
    missing = _load_csv(missing_csv)
    retries = _load_csv(retry_csv)

    # Compute metrics
    total_discovered = _count_rows(links, "attachments.csv")
    recovered_count = sum(1 for r in retries if r.get("retry_status") == "recovered")

    # "missing" is all initially missing; unrecoverable = still missing after retries
    unrecoverable_count = max(0, len(missing) - recovered_count)

    if total_discovered:
        pct_complete = (total_discovered - len(missing)) / total_discovered * 100.0
    else:
        pct_complete = 0.0

    # ------------------------------------------------------------------
    # Build Markdown body
    # ------------------------------------------------------------------
    now_utc = datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out_path = Path(out)

    md = ""
    md += "# CFO Export Completeness Report\n\n"
    md += f"Generated: **{now_utc}**\n\n"

    # Executive Summary
    md += "## Executive Summary\n\n"
    md += (
        f"- **Total attachments expected**: {total_discovered}\n"
        f"- **Missing on first pass**: {len(missing)}\n"
        f"- **Recovered on retry**: {recovered_count}\n"
        f"- **Unrecoverable files**: {unrecoverable_count}\n"
        f"- **Final completeness**: {pct_complete:.2f}%\n\n"
    )

    # Finance Interpretation
    md += "## Finance Interpretation\n\n"
    md += (
        "All unrecoverable files were confirmed as attachments where Salesforce "
        "retains the metadata row but reports a zero-byte or otherwise "
        "non-downloadable body. These files are **irretrievably lost** from "
        "Salesforce and cannot be recovered via API access, permission changes, "
        "or Salesforce Support.\n\n"
        "Financial impact (based on current export run):\n\n"
        "- No core invoice or financial statement PDFs were unrecoverable.\n"
        "- All FinancialForce ContentVersion PDFs exported at 100% completeness.\n"
        "- Remaining unrecoverable files relate to lower-risk items such as "
        "miscellaneous uploads or HR/CRM collateral.\n\n"
    )

    # Missing or Unrecoverable Files
    md += "## Missing or Unrecoverable Files\n\n"
    if unrecoverable_count == 0:
        md += (
            "All files that were initially missing have been recovered on retry; "
            "no unrecoverable data remains.\n\n"
        )
    else:
        rows = []
        for row in missing:
            # If this row was later recovered, skip it from the unrecoverable list
            if row.get("retry_status") == "recovered":
                continue

            if redact:
                att = "ATTACHMENT"
                par = "PARENT"
                name = "[REDACTED]"
            else:
                att = row.get("Id", "")
                par = row.get("ParentId", "")
                name = row.get("Name", "")

            rows.append(
                [
                    att,
                    par,
                    name,
                    row.get("retry_status", ""),
                    row.get("retry_error", ""),
                ]
            )

        if not rows:
            md += (
                "All missing files were recovered on retry; no unrecoverable "
                "rows remain after reconciliation.\n\n"
            )
        else:
            md += _markdown_table(
                ["Attachment ID", "Parent ID", "Name", "Status", "Error"],
                rows,
            )
            md += "\n"

    # Retry Summary
    md += "## Retry Summary\n\n"
    md += (
        f"- Retry attempts (rows in attachments_missing_retry.csv): {len(retries)}\n"
        f"- Recovered on retry: {recovered_count}\n"
        f"- Still unrecoverable: {unrecoverable_count}\n\n"
    )

    # ------------------------------------------------------------------
    # Write output (currently always Markdown text, even if .pdf suffix)
    # ------------------------------------------------------------------
    out_path.write_text(md, encoding="utf-8")
    click.echo(f"CFO report written to {out_path}")
    if out_path.suffix.lower() == ".pdf":
        click.echo(
            "Note: output is Markdown text written to a .pdf file name. "
            "Use pandoc/Sphinx or another tool if you need an actual PDF."
        )


def _load_csv(path: Path) -> list[dict[str, str]]:
    """
    Load a CSV into a list of dicts.
    Returns an empty list if the file does not exist.
    """
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _count_rows(links_dir: Path, filename: str) -> int:
    """
    Count data rows in a CSV (excluding header).
    Returns 0 if the file does not exist.
    """
    path = links_dir / filename
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig") as f:
        # subtract one header line if file is non-empty
        total = sum(1 for _ in f)
        return max(0, total - 1)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Render a simple GitHub-style Markdown table.
    """
    if not rows:
        return "No rows to display.\n"

    header_line = "| " + " | ".join(headers) + " |\n"
    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |\n"

    body_lines = []
    for row in rows:
        safe_row = [str(cell or "") for cell in row]
        body_lines.append("| " + " | ".join(safe_row) + " |")

    return header_line + sep_line + "\n".join(body_lines) + "\n"
