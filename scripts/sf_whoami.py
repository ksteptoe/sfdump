from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from typing import Any


def _request_json(url: str, access_token: str) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        data = resp.read().decode("utf-8")
    try:
        return json.loads(data)
    except Exception:
        return {"_raw": data}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Show current Salesforce identity/org for the active token."
    )
    ap.add_argument(
        "--instance-url",
        default=os.environ.get("SF_INSTANCE_URL", ""),
        help="e.g. https://sondrel.my.salesforce.com",
    )
    ap.add_argument("--api-version", default="60.0", help="REST API version, e.g. 60.0")
    ap.add_argument(
        "--access-token",
        default=os.environ.get("SF_ACCESS_TOKEN", ""),
        help="Override access token",
    )
    ap.add_argument(
        "--check-contentversion-id",
        default="",
        help="Optional ContentVersion Id (069...) to verify visibility",
    )
    args = ap.parse_args()

    instance_url = (args.instance_url or "").strip().rstrip("/")
    if not instance_url:
        raise SystemExit("Missing --instance-url (or SF_INSTANCE_URL).")

    access_token = (args.access_token or "").strip()
    if not access_token:
        from sfdump.sf_auth import get_salesforce_token  # type: ignore

        tok = get_salesforce_token()
        if isinstance(tok, str):
            access_token = tok.strip()
        elif isinstance(tok, dict):
            access_token = str(
                tok.get("access_token") or tok.get("accessToken") or tok.get("token") or ""
            ).strip()
        else:
            access_token = str(
                getattr(tok, "access_token", "") or getattr(tok, "accessToken", "") or ""
            ).strip()

    if not access_token:
        raise SystemExit(
            "Could not obtain access token (set SF_ACCESS_TOKEN or ensure get_salesforce_token works)."
        )

    # 1) OAuth userinfo (who is this token?)
    userinfo_url = f"{instance_url}/services/oauth2/userinfo"
    userinfo = _request_json(userinfo_url, access_token)

    print("== userinfo ==")
    for k in ("preferred_username", "email", "organization_id", "user_id", "username", "name"):
        v = userinfo.get(k) if isinstance(userinfo, dict) else None
        if v:
            print(f"{k}: {v}")
    if isinstance(userinfo, dict) and "organization_id" not in userinfo:
        print("userinfo keys:", sorted(userinfo.keys())[:40])

    # 2) Organization query (org name / sandbox flag)
    soql = "SELECT Id, Name, IsSandbox, InstanceName FROM Organization"
    q = urllib.parse.quote(soql, safe="")
    org_url = f"{instance_url}/services/data/v{args.api_version}/query/?q={q}"
    org_res = _request_json(org_url, access_token)

    print("\n== Organization ==")
    if isinstance(org_res, dict) and org_res.get("records"):
        rec = org_res["records"][0]
        for k in ("Id", "Name", "IsSandbox", "InstanceName"):
            if k in rec:
                print(f"{k}: {rec[k]}")
    else:
        print(org_res)

    # 3) Optional ContentVersion visibility check
    if args.check_contentversion_id:
        cvid = args.check_contentversion_id.strip()
        soql2 = f"SELECT Id, Title, FileExtension, ContentSize, ContentDocumentId FROM ContentVersion WHERE Id = '{cvid}'"
        q2 = urllib.parse.quote(soql2, safe="")
        cv_url = f"{instance_url}/services/data/v{args.api_version}/query/?q={q2}"
        cv_res = _request_json(cv_url, access_token)
        print("\n== ContentVersion check ==")
        print(cv_res)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
