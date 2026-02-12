#!/usr/bin/env python3
"""Quick test: download a single invoice PDF using the Web Server OAuth token.

Uses frontdoor.jsp to establish a browser session, then hits the VF page
directly to render the PDF.

Usage:
    python scripts/test_invoice_pdf.py

Requires: run `sfdump login-web` first to get a user session token.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sfdump.env_loader import load_env_files  # noqa: E402
from sfdump.sf_auth_web import get_web_token  # noqa: E402

load_env_files()

# Test invoice: SIN001673
INVOICE_ID = "a1J2X0000060V6tUAE"
LOGIN_URL = os.environ["SF_LOGIN_URL"]


def main():
    print("Getting web token...")
    token = get_web_token()
    print(f"Token: {token[:10]}...{token[-6:]}")

    # Step 1: Use frontdoor.jsp to establish a session cookie
    session = requests.Session()
    frontdoor_url = f"{LOGIN_URL}/secur/frontdoor.jsp?sid={token}"
    print("Establishing session via frontdoor.jsp...")
    resp = session.get(frontdoor_url, allow_redirects=True)
    print(f"Frontdoor status: {resp.status_code}")
    print(f"Frontdoor final URL: {resp.url}")
    print(f"Cookies: {[c.name for c in session.cookies]}")

    if "sid" not in [c.name for c in session.cookies]:
        print("WARNING: No 'sid' cookie set — session may not be established")
        print(f"Response body (first 500 chars): {resp.text[:500]}")

    # Step 2: Hit the VF page directly to get the PDF
    vf_url = f"{LOGIN_URL}/apex/Sondrel_Sales_Invoice?id={INVOICE_ID}&p=1"
    print(f"\nFetching PDF from VF page: {vf_url}")
    resp = session.get(vf_url)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
    print(f"Content length: {len(resp.content)} bytes")

    if resp.status_code >= 400:
        print(f"Error: {resp.text[:500]}")
        return

    # Check if it's a PDF
    if resp.content[:5] == b"%PDF-":
        print("PDF detected! Saving to test_invoice.pdf")
        with open("test_invoice.pdf", "wb") as f:
            f.write(resp.content)
        print(f"Saved: test_invoice.pdf ({len(resp.content):,} bytes)")
    else:
        print(f"Not a PDF. First 500 bytes: {resp.text[:500]}")


if __name__ == "__main__":
    main()
