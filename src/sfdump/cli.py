from __future__ import annotations

import json
import logging
from typing import Optional

import click

from . import __version__
from .command_objects import objects_cmd
from .logging_config import configure_logging

# Import your API lazily so CLI can exist before API is done.
try:
    from .api import SalesforceAPI, SFConfig
except Exception:  # pragma: no cover
    SalesforceAPI = None  # type: ignore[assignment]
    SFConfig = None  # type: ignore[assignment]

_logger = logging.getLogger(__name__)


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
@click.option(
    "--show-json",
    is_flag=True,
    help="Print raw JSON for identity and limits.",
)
def cmd_login(show_json: bool) -> None:
    """Authenticate and print identity + API limits."""
    if SalesforceAPI is None or SFConfig is None:
        _logger.error("API layer not available. Please implement sfdump.api.")
        raise click.Abort()

    api = SalesforceAPI(SFConfig.from_env())
    _logger.info("Connecting to Salesforce...")
    api.connect()
    _logger.info("Connected. instance=%s, api=%s", api.instance_url, api.api_version)

    who = api.whoami()
    limits = api.limits()

    click.echo(f"Instance URL:   {api.instance_url}")
    click.echo(f"API Version:    {api.api_version}")
    click.echo(f"Org ID:         {who.get('organization_id')}")
    click.echo(f"User ID:        {who.get('user_id')}")
    click.echo(f"Username:       {who.get('preferred_username') or who.get('email')}")
    click.echo(f"Name:           {who.get('name')}")

    core = limits.get("DailyApiRequests", {})
    click.echo(
        f"API Core Used:  {core.get('Max', '?')} max / {core.get('Remaining', '?')} remaining"
    )

    if show_json:
        click.echo("\n# whoami (userinfo)")
        click.echo(json.dumps(who, indent=2))
        click.echo("\n# limits")
        click.echo(json.dumps(limits, indent=2))


@cli.command("query")
@click.argument("soql")
@click.option("--pretty", is_flag=True, help="Pretty-print JSON.")
def cmd_query(soql: str, pretty: bool) -> None:
    """Run a SOQL query."""
    if SalesforceAPI is None or SFConfig is None:
        _logger.error("API layer not available. Please implement sfdump.api.")
        raise click.Abort()

    _logger.debug("Running SOQL: %s", soql)
    api = SalesforceAPI(SFConfig.from_env())
    api.connect()
    res = api.query(soql)
    click.echo(json.dumps(res, indent=2 if pretty else None))


cli.add_command(objects_cmd)
