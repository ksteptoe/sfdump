"""
CLI command to retry downloading missing Attachment and ContentVersion files.
"""

import logging
import os

import click

from .api import SalesforceAPI
from .retry import (
    load_missing_csv,
    retry_missing_attachments,
    retry_missing_content_versions,
)

_logger = logging.getLogger(__name__)


@click.command(name="retry-missing")
@click.option(
    "-d",
    "--export-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Export directory produced by `sfdump files`.",
)
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv).")
def retry_missing_cmd(export_dir: str, verbose: int) -> None:
    """
    Retry downloading files that were flagged as missing by `sfdump verify-files`.
    Produces retry result CSVs under links/.
    """
    # Setup logging based on verbosity flags
    if verbose >= 2:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose == 1:
        logging.getLogger().setLevel(logging.INFO)

    click.echo(f"Retrying missing files under: {export_dir}")

    links_dir = os.path.join(export_dir, "links")
    if not os.path.isdir(links_dir):
        raise click.ClickException(
            f"links/ directory not found under {export_dir} "
            "Did you provide the correct export root?"
        )

    # Missing-file CSVs written by verify-files
    attach_missing_csv = os.path.join(links_dir, "attachments_missing.csv")
    cv_missing_csv = os.path.join(links_dir, "content_versions_missing.csv")

    api = SalesforceAPI()
    api.connect()

    if os.path.isfile(attach_missing_csv):
        click.echo("Retrying missing Attachments...")
        rows = load_missing_csv(attach_missing_csv)
        retry_missing_attachments(api, rows, export_dir, links_dir)
    else:
        click.echo("No attachments_missing.csv found. Skipping attachments.")

    if os.path.isfile(cv_missing_csv):
        click.echo("Retrying missing ContentVersions...")
        rows = load_missing_csv(cv_missing_csv)
        retry_missing_content_versions(api, rows, export_dir, links_dir)
    else:
        click.echo("No content_versions_missing.csv found. Skipping ContentVersions.")

    click.echo("Retry missing files complete.")
