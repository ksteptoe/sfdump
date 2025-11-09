from __future__ import annotations

import click

from .api import SalesforceAPI, SFConfig


@click.command("objects")
@click.option(
    "--all", "show_all", is_flag=True, help="Show all sObjects (default: only queryable)."
)
def objects_cmd(show_all: bool) -> None:
    """List sObjects (queryable by default)."""
    api = SalesforceAPI(SFConfig.from_env())
    api.connect()
    g = api.describe_global()
    sobjs = g.get("sobjects", [])

    def want(s):
        return show_all or s.get("queryable")

    names = sorted(s["name"] for s in sobjs if want(s))
    for n in names:
        click.echo(n)
