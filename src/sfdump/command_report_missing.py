import logging
import os

import click

from .command_analyse_missing import analyse_missing_cmd as _analyse_cmd
from .command_retry_missing import retry_missing_cmd as _retry_cmd
from .command_verify import verify_files_cmd as _verify_cmd
from .report import generate_missing_report

_logger = logging.getLogger(__name__)


@click.command(name="report-missing")
@click.option(
    "--export-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Export directory produced by `sfdump files`.",
)
@click.option("--pdf", is_flag=True, help="Also generate PDF output.")
@click.option(
    "--out",
    type=str,
    default=None,
    help="Base path (with or without extension) for report files. "
    "If omitted, reports are written under links/ with a timestamped name.",
)
@click.option(
    "--logo",
    type=str,
    default=None,
    help="Optional logo image path to embed in the report.",
)
@click.option(
    "--redact",
    is_flag=True,
    help="Redact record IDs, names and URLs to make the report safe for sharing/commit.",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv).")
def report_missing_cmd(
    export_dir: str, pdf: bool, out: str, logo: str, redact: bool, verbose: int
) -> None:
    """
    Generate a unified missing-file report in Markdown, and optionally PDF.
    """

    # Logging level setup
    if verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose == 1:
        logging.getLogger().setLevel(logging.INFO)

    click.echo(f"Generating missing-file report for: {export_dir}")

    links_dir = os.path.join(export_dir, "links")
    if not os.path.isdir(links_dir):
        raise click.ClickException(f"No links/ directory found under: {export_dir}")

    # Step 1: verify-files
    click.echo("Running verify-files...")
    ctx = click.get_current_context()
    ctx.invoke(_verify_cmd, export_dir=export_dir, verbose=verbose)

    # Step 2: retry-missing (only if missing rows exist)
    attach_missing_csv = os.path.join(links_dir, "attachments_missing.csv")
    cv_missing_csv = os.path.join(links_dir, "content_versions_missing.csv")

    if os.path.isfile(attach_missing_csv) or os.path.isfile(cv_missing_csv):
        click.echo("Running retry-missing...")
        ctx.invoke(_retry_cmd, export_dir=export_dir, verbose=verbose)
    else:
        click.echo("No missing CSVs detected; skipping retry-missing.")

    # Step 3: analyse-missing
    click.echo("Running analyse-missing...")
    ctx.invoke(_analyse_cmd, export_dir=export_dir, verbose=verbose)

    # Step 4: Build report
    click.echo("Building Markdown report...")
    md_path, pdf_path = generate_missing_report(
        export_dir=export_dir,
        pdf=pdf,
        out_basename=out,
        logo_path=logo,
        redact=redact,
    )

    click.echo(f"Markdown report written to: {md_path}")
    if pdf:
        if pdf_path:
            click.echo(f"PDF report written to: {pdf_path}")
        else:
            click.echo(
                "PDF generation was requested but failed. "
                "Ensure pandoc (and a LaTeX engine) are installed and on your PATH."
            )
