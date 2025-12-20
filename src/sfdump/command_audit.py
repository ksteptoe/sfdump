from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import click


@click.command(name="build-audit-docs")
@click.option(
    "-d",
    "--export-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Root export directory, e.g. ./exports/export-2025-11-29/files",
)
@click.option(
    "--out-dir",
    default=Path("docs/_generated/audit"),
    show_default=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory where audit Markdown outputs will be written.",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (prints more detail about what was generated).",
)
def audit_docs_cmd(export_dir: Path, out_dir: Path, verbose: int) -> None:
    """
    Build documentation-ready audit results (summary_stats.md + missing_file_analysis.md).

    This command is designed for Admin/Finance documentation:

    - It consumes existing SF dump outputs under <export-dir>/links/.
    - It writes Markdown files under docs/_generated/audit/.
    - docs/_generated/ should be excluded from version control (.gitignore).
    """
    links_dir = export_dir / "links"
    out_dir.mkdir(parents=True, exist_ok=True)

    attachments_meta = links_dir / "attachments.csv"
    missing_csv = links_dir / "attachments_missing.csv"
    retry_csv = links_dir / "attachments_missing_retry.csv"
    analysis_md = links_dir / "missing_file_analysis.md"

    # ------------------------------------------------------------------
    # 1. Compute statistics from CSVs (discovered, missing, recovered)
    # ------------------------------------------------------------------
    discovered = 0
    if attachments_meta.exists():
        with attachments_meta.open(newline="", encoding="utf-8") as f:
            meta_rows = list(csv.DictReader(f))
            discovered = len(meta_rows)

    missing_before_retry = 0
    if missing_csv.exists():
        with missing_csv.open(newline="", encoding="utf-8") as f:
            missing_rows = list(csv.DictReader(f))
            missing_before_retry = len(missing_rows)

    recovered_on_retry = 0
    still_missing_after_retry = 0
    if retry_csv.exists():
        with retry_csv.open(newline="", encoding="utf-8") as f:
            retry_rows = list(csv.DictReader(f))
            for row in retry_rows:
                status = (row.get("retry_status") or "").strip().lower()
                if status == "recovered":
                    recovered_on_retry += 1
                else:
                    still_missing_after_retry += 1

    # Initial and final success metrics
    initial_successful = max(discovered - missing_before_retry, 0)
    final_successful = max(discovered - still_missing_after_retry, 0)

    overall_rate = (final_successful / discovered * 100.0) if discovered else 100.0
    initial_rate = (initial_successful / discovered * 100.0) if discovered else 100.0

    # ------------------------------------------------------------------
    # 2. Write summary_stats.md into docs/_generated/audit
    # ------------------------------------------------------------------
    summary_md = [
        "# Audit Summary Statistics",
        "",
        f"Generated: **{datetime.utcnow().isoformat()} UTC**",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total attachments discovered | **{discovered}** |",
        f"| Successfully downloaded (initial run) | **{initial_successful}** |",
        f"| Missing before retry | **{missing_before_retry}** |",
        f"| Recovered on retry | **{recovered_on_retry}** |",
        f"| Still missing after retry | **{still_missing_after_retry}** |",
        f"| Final successfully available | **{final_successful}** |",
        f"| Initial success rate | **{initial_rate:.2f}%** |",
        f"| Overall success rate after retry | **{overall_rate:.2f}%** |",
        "",
        "> Note: Counts and percentages are derived from the export metadata and",
        "> missing-file analysis CSVs. They are suitable for internal Finance/Audit",
        "> documentation but do not expose individual file names.",
        "",
    ]

    summary_path = out_dir / "summary_stats.md"
    summary_path.write_text("\n".join(summary_md), encoding="utf-8")

    # ------------------------------------------------------------------
    # 3. Copy / adapt missing_file_analysis.md for documentation
    # ------------------------------------------------------------------
    analysis_out = out_dir / "missing_file_analysis.md"
    if analysis_md.exists():
        # Reuse the existing Markdown analysis we already generate
        analysis_out.write_text(analysis_md.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        analysis_out.write_text(
            "No detailed missing file analysis was available at the time of generation.\n",
            encoding="utf-8",
        )

    if verbose:
        click.echo(f"[audit-docs] Export dir: {export_dir}")
        click.echo(f"[audit-docs] Links dir: {links_dir}")
        click.echo(f"[audit-docs] Discovered: {discovered}")
        click.echo(f"[audit-docs] Missing before retry: {missing_before_retry}")
        click.echo(f"[audit-docs] Recovered on retry: {recovered_on_retry}")
        click.echo(f"[audit-docs] Still missing after retry: {still_missing_after_retry}")
        click.echo(f"[audit-docs] Summary written to: {summary_path}")
        click.echo(f"[audit-docs] Analysis written to: {analysis_out}")

    click.echo(f"Audit documentation generated in: {out_dir}")
