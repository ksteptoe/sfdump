from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, cast

import click
from click import Command

from sfdump.command_files_backfill import files_backfill_cmd
from sfdump.sf_auth import get_salesforce_token, run_salesforce_query
from sfdump.sf_auth_web import TOKEN_FILE as WEB_TOKEN_FILE
from sfdump.sf_auth_web import interactive_login

from . import __version__
from .command_analyse_missing import analyse_missing_cmd
from .command_audit import audit_docs_cmd
from .command_audit_missing_files import audit_missing_files_cmd
from .command_build_db import build_db_command
from .command_cfo import cfo_generate_docs, cfo_report
from .command_check_export import check_export_cmd

# Command Files
from .command_csv import csv_cmd
from .command_db_info import db_info_command
from .command_db_viewer import db_viewer_command
from .command_docs_for import docs_for_cmd
from .command_docs_index import docs_index_cmd
from .command_files import files_cmd
from .command_inventory import inventory_cmd
from .command_list_records import list_records_command
from .command_manifest import manifest_cmd
from .command_objects import objects_cmd
from .command_probe import probe_cmd
from .command_rels import rels_cmd
from .command_report_missing import report_missing_cmd
from .command_retry_missing import retry_missing_cmd
from .command_schema import schema_cmd
from .command_sins import sins_cmd
from .command_upgrade import upgrade_cmd
from .command_verify import verify_files_cmd
from .command_view_record import view_record_command
from .command_viewer import viewer_cmd
from .logging_config import configure_logging

# Import your API lazily so CLI can exist before API is done.
try:
    from .api import SalesforceAPI, SFConfig
except Exception:  # pragma: no cover
    SalesforceAPI = None  # type: ignore[assignment]
    SFConfig = None  # type: ignore[assignment]

from .env_loader import load_env_files

_logger = logging.getLogger(__name__)

# Load .env very early, so everything else sees env vars
load_env_files()


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)
@click.version_option(__version__, "--version", prog_name="sfdump")
@click.option(
    "-v",
    "--verbose",
    "loglevel",
    flag_value=logging.INFO,
    default=None,
    help="Enable INFO logs.",
)
@click.option(
    "-vv",
    "--very-verbose",
    "loglevel",
    flag_value=logging.DEBUG,
    help="Enable DEBUG logs.",
)
@click.pass_context
def cli(ctx: click.Context, loglevel: Optional[int]) -> None:
    """SF Dump CLI. Use subcommands like 'login' or 'query'."""
    configure_logging(loglevel)
    _logger.debug("CLI start, version=%s", __version__)

    # Notify novice users about available updates on every invocation
    # Only in interactive terminals (skip in tests / piped output)
    try:
        import sys

        if sys.stderr.isatty():
            from .update_check import is_update_available

            available, current, latest = is_update_available()
            if available:
                click.echo(
                    f"\n  Update available: {current} -> {latest}"
                    f"\n  Run 'sfdump upgrade' or 'pip install --upgrade sfdump'.\n",
                    err=True,
                )
    except Exception:
        pass

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command("login")
def cmd_login() -> None:
    """Fetch and cache a new Salesforce token."""
    try:
        token = get_salesforce_token()
        click.echo("✅  Salesforce token refreshed and cached successfully.")
        click.echo(f"Cache file: {Path.home() / '.sfdump_token.json'}")
        click.echo(f"Token preview: {token[:10]}...{token[-6:]}")
    except Exception as e:
        click.echo(f"❌  Login failed: {e}", err=True)
        raise click.Abort() from None


@cli.command("login-web")
def cmd_login_web() -> None:
    """Login via browser (Web Server OAuth flow with PKCE).

    Opens your browser to Salesforce login. After you authenticate,
    the token is cached locally. Required for operations that need a
    real user session (e.g. invoice PDF generation).
    """
    try:
        click.echo("Opening browser for Salesforce login...")
        click.echo("Press Ctrl+C to cancel.")
        token = interactive_login()
        click.echo("Salesforce web login successful.")
        click.echo(f"Cache file: {WEB_TOKEN_FILE}")
        click.echo(f"Token preview: {token[:10]}...{token[-6:]}")
    except KeyboardInterrupt:
        click.echo("\nLogin cancelled.", err=True)
        raise SystemExit(1) from None
    except Exception as e:
        click.echo(f"Login failed: {e}", err=True)
        raise click.Abort() from None


@cli.command("query")
@click.argument("soql")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON.")
def cmd_query(soql: str, pretty: bool) -> None:
    """Run a SOQL query using Client Credentials flow."""
    try:
        res = run_salesforce_query(soql)
        click.echo(json.dumps(res, indent=2 if pretty else None))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# Cast ensures IDE knows of the Command type
cli.add_command(cast(Command, objects_cmd))
cli.add_command(cast(Command, csv_cmd))
cli.add_command(cast(Command, files_cmd))
cli.add_command(cast(Command, manifest_cmd))
cli.add_command(cast(Command, docs_index_cmd))
cli.add_command(cast(Command, viewer_cmd))
cli.add_command(cast(Command, audit_missing_files_cmd))
cli.add_command(cast(Command, verify_files_cmd))
cli.add_command(cast(Command, retry_missing_cmd))
cli.add_command(cast(Command, analyse_missing_cmd))
cli.add_command(cast(Command, report_missing_cmd))
cli.add_command(cast(Command, audit_docs_cmd))
cli.add_command(cast(Command, cfo_generate_docs))
cli.add_command(cast(Command, build_db_command))
cli.add_command(cast(Command, db_info_command))
cli.add_command(cast(Command, view_record_command))
cli.add_command(cast(Command, list_records_command))
cli.add_command(cast(Command, list_records_command))
cli.add_command(cast(Command, db_viewer_command))
cli.add_command(cast(Command, schema_cmd), "schema")
cli.add_command(cast(Command, rels_cmd))
cli.add_command(cast(Command, docs_for_cmd))
cli.add_command(cast(Command, probe_cmd))
cli.add_command(cast(Command, files_backfill_cmd))
cli.add_command(cast(Command, sins_cmd))
cli.add_command(cast(Command, inventory_cmd))
cli.add_command(cast(Command, check_export_cmd))
cli.add_command(cast(Command, upgrade_cmd))


# Keep the original name (probably "cfo-generate-docs")
cli.add_command(cast(Command, cfo_report))
# Also expose it under the friendlier alias "cfo-report"
cli.add_command(cast(Command, cfo_report), name="cfo-report")


@cli.command("hash-password", hidden=True)
def cmd_hash_password() -> None:
    """Generate a SHA-256 hash for use with SFDUMP_HR_PASSWORD_HASH."""
    import hashlib

    pw = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    digest = hashlib.sha256(pw.encode()).hexdigest()
    click.echo(f"\n{digest}")
    click.echo(f"\nAdd to .env:\n  SFDUMP_HR_PASSWORD_HASH={digest}")


def main() -> None:
    """Entry point for `python -m sfdump.cli`."""
    # Let Click handle argv and exit codes
    cli()


if __name__ == "__main__":
    main()
