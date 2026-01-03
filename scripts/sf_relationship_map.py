#!/usr/bin/env python3
"""Map Salesforce object relationships recursively."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

try:
    from pathlib import Path

    from dotenv import load_dotenv

    # Load .env from project root (parent of scripts directory)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    load_dotenv(project_root / ".env")
except ImportError:
    pass  # dotenv is optional

# Configure output encoding for Windows compatibility
if sys.platform == "win32":
    try:
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _request_json(url: str, access_token: str) -> Any:
    """Make authenticated JSON request to Salesforce API."""
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        data = resp.read().decode("utf-8")
    try:
        return json.loads(data)
    except Exception:
        return {"_raw": data}


def get_object_describe(
    instance_url: str, api_version: str, access_token: str, obj_name: str
) -> dict[str, Any]:
    """Fetch describe metadata for a Salesforce object."""
    desc_url = f"{instance_url}/services/data/v{api_version}/sobjects/{obj_name}/describe"
    result = _request_json(desc_url, access_token)
    if not isinstance(result, dict):
        return {}
    return result


def extract_references(describe: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Extract reference fields from describe metadata.

    Returns list of (field_name, target_objects_csv, relationship_name) tuples.
    """
    fields = describe.get("fields", [])
    refs = []
    for f in fields:
        if f.get("type") == "reference":
            field_name = f.get("name", "")
            targets = ",".join(f.get("referenceTo") or [])
            rel_name = f.get("relationshipName") or ""
            refs.append((field_name, targets, rel_name))
    return sorted(refs, key=lambda t: t[0].lower())


def map_relationships_recursive(
    instance_url: str,
    api_version: str,
    access_token: str,
    obj_name: str,
    depth: int,
    max_depth: int,
    visited: set[str],
    indent: str = "",
) -> None:
    """Recursively map and print object relationships as a tree.

    Args:
        instance_url: Salesforce instance URL
        api_version: API version (e.g., "60.0")
        access_token: OAuth access token
        obj_name: Current object name to explore
        depth: Current depth level
        max_depth: Maximum depth to recurse
        visited: Set of already-visited objects to avoid cycles
        indent: Current indentation string for tree display
    """
    if depth > max_depth:
        return

    if obj_name in visited:
        print(f"{indent}{obj_name} (already visited)")
        return

    visited.add(obj_name)

    # Print current object
    if depth == 0:
        print(f"\n{obj_name}")
    else:
        print(f"{indent}{obj_name}")

    # Fetch describe metadata
    try:
        describe = get_object_describe(instance_url, api_version, access_token, obj_name)
    except Exception as e:
        print(f"{indent}  [ERROR: {e}]")
        return

    if not describe or not describe.get("fields"):
        print(f"{indent}  [No fields found]")
        return

    # Extract reference fields
    refs = extract_references(describe)

    if not refs:
        print(f"{indent}  [No reference fields]")
        return

    # Print reference fields
    for i, (field_name, targets, rel_name) in enumerate(refs):
        is_last = i == len(refs) - 1
        connector = "└─" if is_last else "├─"
        rel_text = f" (rel={rel_name})" if rel_name else ""

        print(f"{indent}  {connector} {field_name} -> {targets}{rel_text}")

        # Recurse into target objects
        if depth < max_depth:
            target_list = [t.strip() for t in targets.split(",") if t.strip()]
            for target_obj in target_list:
                child_indent = indent + ("     " if is_last else "  │  ")
                map_relationships_recursive(
                    instance_url,
                    api_version,
                    access_token,
                    target_obj,
                    depth + 1,
                    max_depth,
                    visited,
                    child_indent,
                )


def main() -> int:
    """Main entry point."""
    ap = argparse.ArgumentParser(
        description="Map Salesforce object relationships recursively.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Map Account relationships (1 level deep)
  python sf_relationship_map.py Account

  # Map custom object relationships (2 levels deep)
  python sf_relationship_map.py c2g__codaPurchaseInvoice__c --max-depth 2

  # Use explicit credentials
  python sf_relationship_map.py Opportunity --instance-url https://myorg.my.salesforce.com --access-token YOUR_TOKEN
        """,
    )
    ap.add_argument(
        "object", help="Salesforce object API name (e.g., Account, Contact, CustomObject__c)"
    )
    ap.add_argument(
        "--max-depth",
        type=int,
        default=1,
        help="Maximum recursion depth (default: 1). Use 0 for current object only, 2+ for deeper exploration.",
    )
    ap.add_argument(
        "--instance-url",
        default=os.environ.get("SF_INSTANCE_URL", ""),
        help="Salesforce instance URL (e.g., https://yourorg.my.salesforce.com)",
    )
    ap.add_argument(
        "--api-version",
        default=os.environ.get("SF_API_VERSION", "60.0"),
        help="REST API version (default: 60.0)",
    )
    ap.add_argument(
        "--access-token",
        default=os.environ.get("SF_ACCESS_TOKEN", ""),
        help="OAuth access token (or set SF_ACCESS_TOKEN env var)",
    )

    args = ap.parse_args()

    # Validate instance URL (also check SF_LOGIN_URL as fallback)
    instance_url = (args.instance_url or "").strip().rstrip("/")
    if not instance_url:
        instance_url = os.environ.get("SF_LOGIN_URL", "").strip().rstrip("/")
    if not instance_url:
        print(
            "ERROR: Missing --instance-url (or SF_INSTANCE_URL/SF_LOGIN_URL environment variable)",
            file=sys.stderr,
        )
        return 1

    # Get access token
    access_token = (args.access_token or "").strip()
    if not access_token:
        try:
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
        except ImportError:
            pass

    if not access_token:
        print(
            "ERROR: Could not obtain access token. Set SF_ACCESS_TOKEN or ensure sfdump.sf_auth works.",
            file=sys.stderr,
        )
        return 1

    # Clean API version
    api_version = (args.api_version or "60.0").lstrip("vV")

    # Map relationships
    print(f"Mapping relationships for: {args.object}")
    print(f"Max depth: {args.max_depth}")
    print(f"Instance: {instance_url}")
    print("=" * 80)

    visited: set[str] = set()
    try:
        map_relationships_recursive(
            instance_url,
            api_version,
            access_token,
            args.object,
            depth=0,
            max_depth=args.max_depth,
            visited=visited,
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 80)
    print(f"Total objects explored: {len(visited)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
