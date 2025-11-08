from __future__ import annotations

import os
from typing import List, Optional

import click

from .api import SalesforceAPI, SFConfig
from .dumper import dump_object_to_csv, fieldnames_for_object
from .exceptions import MissingCredentialsError
from .utils import ensure_dir

# Try to auto-load a .env if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


@click.command("csv")
@click.option("--object", "object_name", required=True, help="sObject name (e.g. Account).")
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output directory.",
)
@click.option(
    "--fields",
    help="Comma-separated field list; default: all queryable non-relationship fields.",
)
@click.option("--where", help="Optional SOQL WHERE clause (without the 'WHERE').")
@click.option("--limit", type=int, help="Optional row limit (client-side stop).")
def csv_cmd(
    object_name: str,
    out_dir: str,
    fields: Optional[str],
    where: Optional[str],
    limit: Optional[int],
) -> None:
    """Dump a single sObject to CSV."""
    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        missing = ", ".join(e.missing)
        msg = (
            f"Missing Salesforce credentials: {missing}\n\n"
            "Set environment variables or create a .env file with:\n"
            "  SF_CLIENT_ID, SF_CLIENT_SECRET, SF_USERNAME, SF_PASSWORD\n"
            "Note: SF_PASSWORD should include your security token if required."
        )
        raise click.ClickException(msg) from e

    ensure_dir(out_dir)
    resolved_fields: Optional[List[str]] = None
    if fields:
        resolved_fields = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        try:
            resolved_fields = fieldnames_for_object(api, object_name)
        except Exception as err:
            raise click.ClickException(f"Failed to describe object '{object_name}'.") from err

    try:
        csv_path, n = dump_object_to_csv(
            api=api,
            object_name=object_name,
            out_dir=os.path.join(out_dir, "csv"),
            fields=resolved_fields,
            where=where,
            limit=limit,
        )
    except Exception as err:
        raise click.ClickException(f"Failed to dump {object_name} to CSV.") from err

    click.echo(f"✅ Wrote {n} rows → {csv_path}")
