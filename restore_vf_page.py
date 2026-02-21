#!/usr/bin/env python3
"""Restore the Sondrel_Sales_Invoice VF page from the backup file.

Usage:
    python restore_vf_page.py

Reads Sondrel_Sales_Invoice_BACKUP.vfp and deploys it back to Salesforce,
reverting any CSS changes made to the invoice template.
"""

import json
import sys
from pathlib import Path

import requests

BACKUP_FILE = Path(__file__).parent / "Sondrel_Sales_Invoice_BACKUP.vfp"
PAGE_ID = "066w00000001YKuAAM"


def main():
    if not BACKUP_FILE.exists():
        print(f"ERROR: Backup file not found: {BACKUP_FILE}", file=sys.stderr)
        sys.exit(1)

    markup = BACKUP_FILE.read_text()
    print(f"Loaded backup: {len(markup)} chars")

    # Read .env
    env = {}
    env_path = Path(__file__).parent / ".env"
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v

    # Get token
    resp = requests.post(
        f'{env["SF_LOGIN_URL"]}/services/oauth2/token',
        data={
            "grant_type": "client_credentials",
            "client_id": env["SF_CLIENT_ID"],
            "client_secret": env["SF_CLIENT_SECRET"],
        },
    )
    auth = resp.json()
    token = auth["access_token"]
    url = auth["instance_url"]

    # Deploy backup
    resp2 = requests.patch(
        f"{url}/services/data/v60.0/tooling/sobjects/ApexPage/{PAGE_ID}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"Markup": markup},
    )

    if resp2.status_code == 204:
        print("SUCCESS: VF page restored to backup version.")
    else:
        print(f"FAILED ({resp2.status_code}): {resp2.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
