from __future__ import annotations

import os

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError
from .files import (
    dump_attachments,
    dump_content_versions,
    estimate_attachments,
    estimate_content_versions,
)
from .utils import ensure_dir

# optional .env loader
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


@click.command("files")
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output directory.",
)
@click.option("--no-content", is_flag=True, help="Skip ContentVersion downloads.")
@click.option("--no-attachments", is_flag=True, help="Skip legacy Attachment downloads.")
@click.option(
    "--content-where",
    help="Extra AND filter for ContentVersion (without WHERE).",
)
@click.option(
    "--attachments-where",
    help="WHERE clause for Attachment (without WHERE).",
)
@click.option(
    "--max-workers",
    type=int,
    default=8,
    show_default=True,
    help="Parallel download workers.",
)
@click.option(
    "--estimate-only",
    is_flag=True,
    help="Do not download anything; just estimate counts and total bytes.",
)
def files_cmd(
    out_dir: str,
    no_content: bool,
    no_attachments: bool,
    content_where: str | None,
    attachments_where: str | None,
    max_workers: int,
    estimate_only: bool,
) -> None:
    """Download Salesforce files: ContentVersion (latest) & legacy Attachment."""
    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        missing = ", ".join(e.missing)
        msg = (
            f"Missing Salesforce credentials: {missing}\n\n"
            "Set env vars or create a .env file with SF_CLIENT_ID, SF_CLIENT_SECRET, "
            "SF_USERNAME, SF_PASSWORD."
        )
        raise click.ClickException(msg) from e

    results: list[dict] = []

    if estimate_only:
        # Estimation mode: no filesystem writes.
        if not no_content:
            results.append(
                estimate_content_versions(
                    api,
                    where=content_where,
                )
            )
        if not no_attachments:
            results.append(
                estimate_attachments(
                    api,
                    where=attachments_where,
                )
            )
    else:
        # Real download mode.
        ensure_dir(out_dir)
        try:
            if not no_content:
                results.append(
                    dump_content_versions(
                        api,
                        out_dir,
                        where=content_where,
                        max_workers=max_workers,
                    )
                )

            if not no_attachments:
                results.append(
                    dump_attachments(
                        api,
                        out_dir,
                        where=attachments_where,
                        max_workers=max_workers,
                    )
                )
        except KeyboardInterrupt as exc:
            # Graceful abort on Ctrl+C
            click.echo(
                f"\nAborted by user (Ctrl+C). Partial output may remain in: {out_dir}",
                err=True,
            )
            raise click.Abort() from exc

    if not results:
        raise click.ClickException(
            "Nothing to do: both ContentVersion and Attachment were disabled."
        )

    def _format_bytes(num: float) -> str:
        """Human-readable byte format, like du -h."""
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        value = num
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                return f"{value:,.1f} {unit}"
            value /= 1024.0
        return f"{value:,.1f} PB"

    # short human summary per kind
    def line(r: dict) -> str:
        bytes_val = int(r.get("bytes") or 0)
        human = _format_bytes(float(bytes_val))
        return f"{r['kind']}: {r['count']} files, {human} ({bytes_val:,.0f} bytes) → {r['root']}"

    total_files = 0
    total_bytes = 0

    for r in results:
        click.echo(line(r))
        total_files += int(r.get("count") or 0)
        total_bytes += int(r.get("bytes") or 0)

    # overall total
    total_human = _format_bytes(float(total_bytes))
    click.echo(f"Total: {total_files} files, {total_human} ({total_bytes:,.0f} bytes)")

    if not estimate_only:
        click.echo(f"Metadata CSVs are under: {os.path.join(out_dir, 'links')}")
