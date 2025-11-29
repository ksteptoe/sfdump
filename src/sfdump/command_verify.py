"""
Verification command for checking exported files against metadata CSVs.
"""

import logging
import os

import click

from .verify import (
    verify_attachments,
    verify_content_versions,
)

_logger = logging.getLogger(__name__)


@click.command(name="verify-files")
@click.option(
    "--export-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to the export directory produced by 'sfdump files'.",
)
def verify_files_cmd(export_dir: str) -> None:
    """
    Verify that all exported Attachment and ContentVersion files exist,
    are non-zero, and match their SHA256 checksums.
    """
    click.echo(f"Verifying export under: {export_dir}")

    links_dir = os.path.join(export_dir, "links")
    if not os.path.isdir(links_dir):
        raise click.ClickException(
            f"links/ directory not found under {export_dir}. "
            "Did you pass the correct --export-dir?"
        )

    attach_meta = os.path.join(links_dir, "attachments.csv")
    cv_meta = os.path.join(links_dir, "content_versions.csv")

    if not os.path.isfile(attach_meta):
        _logger.warning("attachments.csv not found; skipping attachment verification.")
    else:
        click.echo("Verifying Attachments...")
        verify_attachments(attach_meta, export_dir)

    if not os.path.isfile(cv_meta):
        _logger.warning("content_versions.csv not found; skipping ContentVersion verification.")
    else:
        click.echo("Verifying ContentVersions...")
        verify_content_versions(cv_meta, export_dir)

    click.echo("Verification complete.")
