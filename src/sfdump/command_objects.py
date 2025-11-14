from __future__ import annotations

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError


@click.command("objects")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    help="Show all sObjects (default: only queryable).",
)
def objects_cmd(show_all: bool) -> None:
    """List sObjects (queryable by default).

    Uses environment-based Salesforce auth (see `sfdump login --help`).
    """
    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        # Friendly error + tips (include those that are missing)
        needed = ", ".join(e.missing)
        msg = (
            f"Missing Salesforce credentials: {needed}\n\n"
            "Set these environment variables (or create a .env file), e.g. for "
            "client-credentials auth:\n"
            "  SF_AUTH_FLOW=client_credentials\n"
            "  SF_CLIENT_ID=...             # Connected App Consumer Key\n"
            "  SF_CLIENT_SECRET=...         # Connected App Client Secret\n"
            "  SF_LOGIN_URL=https://login.salesforce.com  # or your custom domain URL\n"
            "  SF_API_VERSION=v60.0         # optional; will auto-discover if omitted\n\n"
            "Tip: run `sfdump login --help` for more details on configuration."
        )
        raise click.ClickException(msg) from e

    # continue as before
    g = api.describe_global()
    sobjs = g.get("sobjects", [])

    def want(s: dict) -> bool:
        return show_all or s.get("queryable")

    names = sorted(s["name"] for s in sobjs if want(s))
    for n in names:
        click.echo(n)
