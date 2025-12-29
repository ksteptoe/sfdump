from __future__ import annotations

import pandas as pd

# Per-object “good defaults” for list/preview display.
IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": ["Name", "Type", "BillingCountry"],
    "Opportunity": ["Name", "StageName", "Amount", "CloseDate"],
    "OpportunityLineItem": ["Name", "Quantity", "UnitPrice", "TotalPrice"],
    "Contact": ["Name", "Email", "Phone", "Title"],
    "c2g__codaInvoice__c": [
        "Name",
        "c2g__InvoiceNumber__c",
        "c2g__Account__c",
        "c2g__InvoiceDate__c",
    ],
    "c2g__codaInvoiceLineItem__c": ["Name", "c2g__NetValue__c", "c2g__Product__c"],
}


COMMON_LABEL_FIELDS = ["Name", "Subject", "Title", "DocumentTitle"]


def get_important_fields(api_name: str) -> list[str]:
    return IMPORTANT_FIELDS.get(api_name, []).copy()


def select_display_columns(api_name: str, df: pd.DataFrame, show_all_fields: bool) -> list[str]:
    """
    Decide which columns to show for a record DataFrame in the UI.
    """
    if df is None or df.empty:
        return []

    cols = list(df.columns)

    if show_all_fields:
        return cols

    wanted: list[str] = []

    # Always prefer Id if present (but not necessarily show it first)
    if "Id" in cols:
        wanted.append("Id")

    # Important fields first
    for c in get_important_fields(api_name):
        if c in cols and c not in wanted:
            wanted.append(c)

    # Then common label-ish fields
    for c in COMMON_LABEL_FIELDS:
        if c in cols and c not in wanted:
            wanted.append(c)

    # Then a few time-ish fields
    for c in ["CreatedDate", "LastModifiedDate"]:
        if c in cols and c not in wanted:
            wanted.append(c)

    # If we still have almost nothing, just take the first N columns
    if len(wanted) < 3:
        for c in cols:
            if c not in wanted:
                wanted.append(c)
            if len(wanted) >= 12:
                break

    return wanted
