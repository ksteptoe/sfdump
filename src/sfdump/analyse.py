"""
analyse missing Attachments and ContentVersions to identify impacted parent records.
"""

import csv
import logging
import os
from typing import Dict, List

_logger = logging.getLogger(__name__)


# Standard Salesforce ID prefix → object name mapping
PREFIX_MAP = {
    "001": "Account",
    "003": "Contact",
    "006": "Opportunity",
    "005": "User",
    "00Q": "Lead",
    "500": "Case",
    "701": "Campaign",
    "00P": "Attachment",  # child object
    "069": "ContentVersion",
    "068": "ContentDocument",
    # Custom objects start with a02, a03, etc. but we infer generically.
}


def infer_object_from_id(sf_id: str) -> str:
    """Infer the Salesforce object type from the 3-char prefix."""
    if not sf_id or len(sf_id) < 3:
        return "Unknown"
    prefix = sf_id[:3]
    if prefix in PREFIX_MAP:
        return PREFIX_MAP[prefix]
    # Likely a custom object
    if prefix.startswith("a"):
        return "CustomObject"
    return "Unknown"


def _load_missing(path: str) -> List[Dict[str, str]]:
    """Load missing-files CSV (attachments_missing.csv or content_versions_missing.csv)."""
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _safe_query_parent(api, obj: str, parent_id: str) -> str:
    """Try to retrieve a 'Name' field or best alternative from the parent."""
    try:
        # Try primary name field
        soql = f"SELECT Name FROM {obj} WHERE Id = '{parent_id}'"
        rec = api.query(soql)
        if rec and isinstance(rec, dict) and rec.get("records"):
            return rec["records"][0].get("Name", "")
    except Exception:
        pass

    # As fallback, try common financial fields directly
    for field in [
        "InvoiceNumber",
        "Invoice_Number__c",
        "c2g__InvoiceNumber__c",
        "BillingCompany",
        "Title",
        "Subject",
    ]:
        try:
            soql = f"SELECT {field} FROM {obj} WHERE Id = '{parent_id}'"
            rec = api.query(soql)
            if rec and isinstance(rec, dict) and rec.get("records"):
                return rec["records"][0].get(field, "")
        except Exception:
            continue

    return ""


def analyse_missing_files(export_dir: str, api) -> str:
    """
    Prepare a consolidated report of which parent records have missing files.
    Returns the full path to the output analysis CSV.
    """
    links_dir = os.path.join(export_dir, "links")
    attach_missing_csv = os.path.join(links_dir, "attachments_missing.csv")
    cv_missing_csv = os.path.join(links_dir, "content_versions_missing.csv")

    missing_attachments = _load_missing(attach_missing_csv)
    missing_cv = _load_missing(cv_missing_csv)

    all_missing = []
    for r in missing_attachments:
        r["_kind"] = "Attachment"
        all_missing.append(r)
    for r in missing_cv:
        r["_kind"] = "ContentVersion"
        all_missing.append(r)

    if not all_missing:
        _logger.info("No missing rows found across attachments or content versions.")
        out_csv = os.path.join(links_dir, "missing_file_analysis.csv")
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Message"])
            writer.writerow(["No missing files detected."])
        return out_csv

    # Group by ParentId
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for r in all_missing:
        pid = r.get("ParentId") or ""
        grouped.setdefault(pid, []).append(r)

    analysis_rows = []

    for parent_id, rows in grouped.items():
        obj = infer_object_from_id(parent_id)
        attachment_ids = [r.get("Id") for r in rows]

        parent_name = _safe_query_parent(api, obj, parent_id) if obj != "Unknown" else ""

        analysis_rows.append(
            {
                "ParentId": parent_id,
                "ParentObject": obj,
                "MissingCount": len(rows),
                "MissingKinds": ";".join(sorted({r["_kind"] for r in rows})),
                "ParentName": parent_name,
                "AttachmentIds": ";".join(attachment_ids),
                "ParentRecordUrl": f"{api.instance_url}/{parent_id}",
            }
        )

    out_csv = os.path.join(links_dir, "missing_file_analysis.csv")
    fieldnames = [
        "ParentId",
        "ParentObject",
        "MissingCount",
        "MissingKinds",
        "ParentName",
        "AttachmentIds",
        "ParentRecordUrl",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in analysis_rows:
            writer.writerow(r)

    _logger.info(
        "analyse_missing_files: wrote %d grouped rows → %s",
        len(analysis_rows),
        out_csv,
    )

    return out_csv
