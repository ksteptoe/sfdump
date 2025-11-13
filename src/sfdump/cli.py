from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, cast

import click
from click import Command

from sfdump.sf_auth import get_salesforce_token, run_salesforce_query

from . import __version__

# Command Files
from .command_csv import csv_cmd
from .command_files import files_cmd
from .command_manifest import manifest_cmd
from .command_objects import objects_cmd
from .logging_config import configure_logging

try:
    from dotenv import load_dotenv  # optional

    load_dotenv()
except Exception:
    pass

# Import your API lazily so CLI can exist before API is done.
try:
    from .api import SalesforceAPI, SFConfig
except Exception:  # pragma: no cover
    SalesforceAPI = None  # type: ignore[assignment]
    SFConfig = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)


# --- Optional .env loading ---
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Try to load .env or .dotenv from project root or current dir
if load_dotenv:
    # Prefer .env, fallback to .dotenv
    for candidate in (".env", ".dotenv"):
        env_path = Path.cwd() / candidate
        if env_path.exists():
            load_dotenv(env_path)
            logging.getLogger(__name__).debug("Loaded environment variables from %s", env_path)
            break
else:
    logging.getLogger(__name__).warning("python-dotenv not installed; skipping .env loading.")


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
