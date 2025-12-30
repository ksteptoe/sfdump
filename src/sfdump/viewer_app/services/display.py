from __future__ import annotations

from typing import Iterable

import pandas as pd

# A small curated set per object. You can extend this over time.
IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": [
        "Name",
        "Type",
        "Industry",
        "BillingCity",
        "BillingCountry",
        "Website",
        "Phone",
        "OwnerId",
    ],
    "Opportunity": ["Name", "StageName", "Amount", "CloseDate", "AccountId", "OwnerId"],
    "Contact": ["Name", "FirstName", "LastName", "Email", "Phone", "AccountId", "OwnerId"],
    "Case": ["CaseNumber", "Subject", "Status", "Priority", "AccountId", "ContactId", "OwnerId"],
    # Common FF / custom-ish:
    "c2g__codaInvoice__c": [
        "Name",
        "c2g__Account__c",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__Total__c",
    ],
    "fferpcore__BillingDocument__c": [
        "Name",
        "fferpcore__Account__c",
        "fferpcore__Status__c",
        "fferpcore__Total__c",
    ],
    "ContentDocumentLink": ["LinkedEntityId", "ContentDocumentId", "ShareType", "Visibility"],
}


def get_important_fields(api_name: str) -> list[str]:
    """
    Return the "important" field list for an object. If unknown, return [].
    """
    return IMPORTANT_FIELDS.get(api_name, [])


def _ensure_list(x: Iterable[str] | None) -> list[str]:
    return list(x) if x else []


def select_display_columns(
    api_name: str,
    df: pd.DataFrame,
    show_all_fields: bool = False,
    *,
    show_ids: bool = False,
) -> list[str]:
    """
    Decide which columns to show for a child dataframe / list view.

    Signature matches db_app usage:
        select_display_columns(api_name, df, show_all_fields)

    If show_all_fields is True: show everything (optionally hiding Id columns unless show_ids).
    Otherwise: show important fields if present, falling back to common label columns.
    """
    cols = _ensure_list(getattr(df, "columns", []))

    if not cols:
        return []

    if show_all_fields:
        if show_ids:
            return cols
        return [c for c in cols if c.lower() != "id" and not c.lower().endswith("id")]

    important = [c for c in get_important_fields(api_name) if c in cols]

    # Fallback label-ish columns
    label_candidates = ["Name", "Subject", "Title", "DocumentTitle", "StageName", "Status"]
    label_cols = [c for c in label_candidates if c in cols]

    # Always try to include Id for navigation (even if we hide it visually later)
    base = []
    if "Id" in cols:
        base.append("Id")

    chosen = base + important
    for c in label_cols:
        if c not in chosen:
            chosen.append(c)

    # Keep it bounded but useful
    chosen = chosen[:12] if len(chosen) > 12 else chosen

    # If user doesn't want Id columns shown, drop them from the final display set
    if not show_ids:
        chosen = [c for c in chosen if c.lower() != "id" and not c.lower().endswith("id")]

    # Guarantee we show something
    if not chosen:
        chosen = cols[:8]

    return chosen
