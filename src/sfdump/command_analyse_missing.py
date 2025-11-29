"""
CLI command to analyse missing Attachment and ContentVersion files
and determine which parent records are impacted.
"""

import logging
import os

import click

from .analyse import analyse_missing_files
from .api import SalesforceAPI

_logger = logging.getLogger(__name__)


@click.command(name="analyse-missing")
@click.option(
    "--export-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Export directory produced by `sfdump files`.",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv).")
def analyse_missing_cmd(export_dir: str, verbose: int) -> None:
    """
    Analyse which parent records are affected by missing or unrecoverable
    Attachments and ContentVersions.
    Produces `missing_file_analysis.csv` under links/.
    """
    # Setup logging based on verbosity flags
    if verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose == 1:
        logging.getLogger().setLevel(logging.INFO)

    click.echo(f"Analyzing missing file impact under: {export_dir}")

    links_dir = os.path.join(export_dir, "links")
    if not os.path.isdir(links_dir):
        raise click.ClickException(
            f"links/ directory not found in {export_dir}. Did you provide the correct export root?"
        )

    # Prepare Salesforce API for optional parent lookups
    api = SalesforceAPI()
    api.connect()

    out_csv = analyse_missing_files(export_dir, api)
    click.echo(f"Analysis complete. Report written to: {out_csv}")
