#!/usr/bin/env python3
"""Quick test: download a single invoice PDF using the Web Server OAuth token.

Tries multiple approaches to establish a session and fetch the VF page PDF.

Usage:
    python scripts/test_invoice_pdf.py

Requires: run `sfdump login-web` first to get a user session token.
"""

import os
import sys
from http.cookiejar import Cookie
from urllib.parse import urlparse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sfdump.env_loader import load_env_files  # noqa: E402
from sfdump.sf_auth_web import get_web_token  # noqa: E402

load_env_files()

# Test invoice: SIN001673
INVOICE_ID = "a1J2X0000060V6tUAE"
LOGIN_URL = os.environ["SF_LOGIN_URL"]
DOMAIN = urlparse(LOGIN_URL).hostname


def _make_cookie(name, value, domain):
    """Create a cookie for the requests session."""
    return Cookie(
        version=0,
        name=name,
        value=value,
        port=None,
        port_specified=False,
        domain=domain,
        domain_specified=True,
        domain_initial_dot=False,
        path="/",
        path_specified=True,
        secure=True,
        expires=None,
        discard=True,
        comment=None,
        comment_url=None,
        rest={},
    )


def try_manual_cookie(token):
    """Approach 1: Manually set the sid cookie and hit VF page."""
    print("\n=== Approach 1: Manual sid cookie ===")
    session = requests.Session()
    session.cookies.set_cookie(_make_cookie("sid", token, DOMAIN))

    vf_url = f"{LOGIN_URL}/apex/Sondrel_Sales_Invoice?id={INVOICE_ID}&p=1"
    print(f"Fetching: {vf_url}")
    resp = session.get(vf_url, allow_redirects=False)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
    print(f"Content length: {len(resp.content)} bytes")

    if resp.status_code in (301, 302):
        print(f"Redirect to: {resp.headers.get('Location', 'unknown')}")
        return None

    if resp.content[:5] == b"%PDF-":
        return resp.content

    print(f"Not a PDF. First 300 bytes: {resp.text[:300]}")
    return None


def try_bearer_header(token):
    """Approach 2: Use Bearer token header directly on VF page."""
    print("\n=== Approach 2: Bearer Authorization header ===")
    vf_url = f"{LOGIN_URL}/apex/Sondrel_Sales_Invoice?id={INVOICE_ID}&p=1"
    print(f"Fetching: {vf_url}")
    resp = requests.get(
        vf_url,
        headers={"Authorization": f"Bearer {token}"},
        allow_redirects=False,
    )
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
    print(f"Content length: {len(resp.content)} bytes")

    if resp.status_code in (301, 302):
        print(f"Redirect to: {resp.headers.get('Location', 'unknown')}")
        return None

    if resp.content[:5] == b"%PDF-":
        return resp.content

    print(f"Not a PDF. First 300 bytes: {resp.text[:300]}")
    return None


def try_frontdoor_no_redirect(token):
    """Approach 3: frontdoor.jsp without following redirects, then manual cookie."""
    print("\n=== Approach 3: frontdoor.jsp (no auto-redirect) ===")
    session = requests.Session()
    frontdoor_url = f"{LOGIN_URL}/secur/frontdoor.jsp?sid={token}"
    resp = session.get(frontdoor_url, allow_redirects=False)
    print(f"Frontdoor status: {resp.status_code}")
    if resp.status_code in (301, 302):
        print(f"Redirect to: {resp.headers.get('Location', 'unknown')}")
    print(f"Cookies after frontdoor: {[(c.name, c.domain) for c in session.cookies]}")

    # Even if frontdoor didn't set sid, manually add it and try
    if "sid" not in [c.name for c in session.cookies]:
        session.cookies.set_cookie(_make_cookie("sid", token, DOMAIN))
        # Also try with dot-prefixed domain
        session.cookies.set_cookie(_make_cookie("sid", token, f".{DOMAIN}"))
        print("Manually added sid cookie")

    vf_url = f"{LOGIN_URL}/apex/Sondrel_Sales_Invoice?id={INVOICE_ID}&p=1"
    print(f"Fetching: {vf_url}")
    resp = session.get(vf_url, allow_redirects=False)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")

    if resp.status_code in (301, 302):
        print(f"Redirect to: {resp.headers.get('Location', 'unknown')}")
        return None

    if resp.content[:5] == b"%PDF-":
        return resp.content

    print(f"Not a PDF. First 300 bytes: {resp.text[:300]}")
    return None


def main():
    print("Getting web token...")
    token = get_web_token()
    print(f"Token: {token[:10]}...{token[-6:]}")
    print(f"Domain: {DOMAIN}")

    for approach in [try_manual_cookie, try_bearer_header, try_frontdoor_no_redirect]:
        pdf = approach(token)
        if pdf:
            print("\nPDF detected! Saving to test_invoice.pdf")
            with open("test_invoice.pdf", "wb") as f:
                f.write(pdf)
            print(f"Saved: test_invoice.pdf ({len(pdf):,} bytes)")
            return

    print("\nAll approaches failed.")


if __name__ == "__main__":
    main()
