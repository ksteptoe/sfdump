from __future__ import annotations

import os
from datetime import datetime, timezone

import click

from .api import SalesforceAPI, SFConfig
from .exceptions import MissingCredentialsError
from .manifest import Manifest, scan_files, scan_objects, write_manifest


@click.command("manifest")
@click.option(
    "--out",
    "out_dir",
    required=True,
    type=click.Path(file_okay=False),
    help="Output directory that contains csv/, links/, files/ etc.",
)
@click.option(
    "--offline", is_flag=True, help="Skip Salesforce login; write manifest with empty org info."
)
def manifest_cmd(out_dir: str, offline: bool) -> None:
    """Generate manifest.json summarising the dump under --out."""
    org_id = username = instance_url = api_version = ""

    if not offline:
        api = SalesforceAPI(SFConfig.from_env())
        try:
            api.connect()
            who = api.whoami()
            org_id = who.get("organization_id", "") or ""
            username = who.get("preferred_username") or who.get("email") or ""
            instance_url = api.instance_url or ""
            api_version = api.api_version or ""
        except MissingCredentialsError as e:
            # Graceful fallback to offline if creds missing
            missing = ", ".join(e.missing)
            click.echo(
                f"Warning: missing credentials ({missing}); writing manifest in offline mode.",
                err=True,
            )
        except Exception as err:
            # Keep it friendly: allow offline manifest if login fails
            raise click.ClickException(f"Salesforce login failed: {err}") from err

    csv_root = os.path.join(out_dir, "csv")
    objects = scan_objects(csv_root)
    files = scan_files(out_dir)

    m = Manifest(
        generated_utc=datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        org_id=org_id,
        username=username,
        instance_url=instance_url,
        api_version=api_version,
        csv_root=csv_root,
        files=files,
        objects=objects,
    )
    path = os.path.join(out_dir, "manifest.json")
    write_manifest(path, m)
    click.echo(f"✅ Wrote manifest → {os.path.abspath(path)}")
