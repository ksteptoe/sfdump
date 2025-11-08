from __future__ import annotations

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError

# try to load .env silently if python-dotenv is available
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:
    pass


@click.command("objects")
@click.option(
    "--all", "show_all", is_flag=True, help="Show all sObjects (default: only queryable)."
)
def objects_cmd(show_all: bool) -> None:
    """List sObjects (queryable by default)."""
    api = SalesforceAPI(SFConfig.from_env())
    try:
        api.connect()
    except MissingCredentialsError as e:
        # Friendly error + tips (include those that are missing)
        needed = ", ".join(e.missing)
        msg = (
            f"Missing Salesforce credentials: {needed}\n\n"
            "Set these environment variables (or create a .env file):\n"
            "  SF_CLIENT_ID=...\n"
            "  SF_CLIENT_SECRET=...\n"
            "  SF_USERNAME=you@example.com\n"
            "  SF_PASSWORD='password+token'  # append security token if required\n\n"
            "Tip: you can run `sfdump login --help` for more info."
        )
        raise click.ClickException(msg) from e
    # continue as before
    g = api.describe_global()
    sobjs = g.get("sobjects", [])

    def want(s):
        return show_all or s.get("queryable")

    names = sorted(s["name"] for s in sobjs if want(s))
    for n in names:
        click.echo(n)
