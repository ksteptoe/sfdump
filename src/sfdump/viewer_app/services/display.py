from __future__ import annotations

from typing import Iterable

import pandas as pd  # type: ignore[import-not-found]

# Pragmatic defaults – keep these small and user-friendly.
IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": ["Name", "Type", "Industry", "BillingCountry", "BillingCity", "Website"],
    "Opportunity": [
        "Name",
        "StageName",
        "CloseDate",
        "Amount",
        "CurrencyIsoCode",
        "AccountId",
        "AccountName",
    ],
    "Contact": ["Name", "FirstName", "LastName", "Email", "Phone", "AccountId"],
    "Case": ["CaseNumber", "Subject", "Status", "Priority", "AccountId", "ContactId"],
    "ContentDocumentLink": ["ContentDocumentId", "LinkedEntityId", "ShareType", "Visibility"],
    "ContentVersion": ["Title", "FileExtension", "ContentSize", "VersionNumber", "CreatedDate"],
    "Attachment": ["Name", "ContentType", "BodyLength", "ParentId", "CreatedDate"],
    # Common Finance / FFA-ish
    "c2g__codaInvoice__c": [
        "Name",
        "c2g__InvoiceDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        "CurrencyIsoCode",
    ],
    "fferpcore__BillingDocument__c": [
        "Name",
        "fferpcore__InvoiceDate__c",
        "fferpcore__Status__c",
        "fferpcore__Total__c",
        "fferpcore__Outstanding__c",
        "CurrencyIsoCode",
    ],
}


# Common “good to show if present” for any object
GENERIC_PREFERRED: list[str] = [
    "Name",
    "Subject",
    "Title",
    "DocumentTitle",
    "StageName",
    "Status",
    "CloseDate",
    "Amount",
    "TotalAmount",
    "Balance",
    "CurrencyIsoCode",
    "CreatedDate",
    "LastModifiedDate",
]


def get_important_fields(api_name: str) -> list[str]:
    """Return a small ordered list of fields that are typically meaningful for this object."""
    return IMPORTANT_FIELDS.get(api_name, []).copy()


def _stable_unique(seq: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def select_display_columns(
    api_name: str,
    df: "pd.DataFrame",
    show_all_fields: bool,
    *,
    show_ids: bool = False,
    max_cols: int = 25,
) -> list[str]:
    """
    Decide which columns to show in a relationship table.

    Rules:
      - if show_all_fields: show everything (but keep Id optional)
      - else: show important fields + a few generic preferred + Id optional
      - preserve original df column ordering where possible
    """
    cols = list(df.columns)

    if show_all_fields:
        if show_ids:
            return cols
        return [c for c in cols if c != "Id"]

    important = get_important_fields(api_name)
    wanted = _stable_unique(important + GENERIC_PREFERRED)

    # Add Id at end if requested and present
    if show_ids and "Id" in cols and "Id" not in wanted:
        wanted.append("Id")

    # Filter to those actually present, preserving the df order
    present = set(cols)
    ordered = [c for c in cols if c in wanted and c in present]

    # If we got nothing, fall back to "everything but maybe Id"
    if not ordered:
        ordered = cols if show_ids else [c for c in cols if c != "Id"]

    # Cap for usability
    if len(ordered) > max_cols:
        ordered = ordered[:max_cols]

    return ordered
