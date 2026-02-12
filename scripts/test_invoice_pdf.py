#!/usr/bin/env python3
"""Quick test: download a single invoice PDF using the Web Server OAuth token.

Tries multiple approaches to fetch the invoice PDF.

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


def try_apex_rest(token):
    """Approach 1: Apex REST endpoint (now with real session ID, not JWT)."""
    print("\n=== Approach 1: Apex REST endpoint ===")
    url = f"{LOGIN_URL}/services/apexrest/sfdump/invoice-pdf?id={INVOICE_ID}"
    print(f"Fetching: {url}")
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
    print(f"Content length: {len(resp.content)} bytes")

    if resp.status_code >= 400:
        print(f"Error: {resp.text[:500]}")
        return None

    if resp.content[:5] == b"%PDF-":
        return resp.content

    print(f"Not a PDF. First 300 bytes: {resp.content[:300]}")
    return None


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
    """Approach 2: Manually set the sid cookie and hit VF page."""
    print("\n=== Approach 2: Manual sid cookie on VF page ===")
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


def try_tooling_anonymous_apex(token):
    """Approach 3: Execute anonymous Apex to test getContentAsPdf capability."""
    print("\n=== Approach 3: Tooling API executeAnonymous ===")
    api_version = os.environ.get("SF_API_VERSION", "v60.0")
    apex_code = (
        "PageReference pdfPage = Page.Sondrel_Sales_Invoice;"
        f"pdfPage.getParameters().put('id', '{INVOICE_ID}');"
        "pdfPage.getParameters().put('p', '1');"
        "Blob pdfBlob = pdfPage.getContentAsPdf();"
        "System.debug('PDF_SIZE=' + pdfBlob.size());"
    )
    url = f"{LOGIN_URL}/services/data/{api_version}/tooling/executeAnonymous/"
    print("Executing anonymous Apex...")
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        params={"anonymousBody": apex_code},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code >= 400:
        print(f"Error: {resp.text[:500]}")
    else:
        data = resp.json()
        print(f"Compiled: {data.get('compiled')}")
        print(f"Success: {data.get('success')}")
        if not data.get("success"):
            print(f"Exception: {data.get('exceptionMessage')}")
            print(f"Stack trace: {data.get('exceptionStackTrace')}")
        else:
            print("getContentAsPdf() WORKS with this session!")
            print("(But we need the Apex REST endpoint to return the bytes)")
    return None  # This approach only tests capability


def main():
    print("Getting web token...")
    token = get_web_token()
    print(f"Token: {token[:10]}...{token[-6:]}")
    print(f"Token type: {'JWT' if token.startswith('eyJ') else 'Session ID'}")
    print(f"Domain: {DOMAIN}")

    # Try Apex REST first (most likely to work with real session ID)
    pdf = try_apex_rest(token)
    if pdf:
        print("\nPDF detected! Saving to test_invoice.pdf")
        with open("test_invoice.pdf", "wb") as f:
            f.write(pdf)
        print(f"Saved: test_invoice.pdf ({len(pdf):,} bytes)")
        return

    # Try manual cookie on VF page
    pdf = try_manual_cookie(token)
    if pdf:
        print("\nPDF detected! Saving to test_invoice.pdf")
        with open("test_invoice.pdf", "wb") as f:
            f.write(pdf)
        print(f"Saved: test_invoice.pdf ({len(pdf):,} bytes)")
        return

    # Test if getContentAsPdf works at all with this session
    try_tooling_anonymous_apex(token)

    print("\nDirect PDF fetch failed. See anonymous Apex result above.")


if __name__ == "__main__":
    main()
