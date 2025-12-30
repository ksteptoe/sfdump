from __future__ import annotations

from typing import Iterable, Optional

# Keep this file dependency-light: avoid importing pandas at module import time.


IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": ["Name", "Type", "Industry", "BillingCountry", "BillingCity", "Website"],
    "Opportunity": [
        "Name",
        "StageName",
        "Amount",
        "CloseDate",
        "AccountId",
        "OwnerId",
        "CurrencyIsoCode",
    ],
    "ContentDocumentLink": ["LinkedEntityId", "ContentDocumentId", "Visibility", "ShareType"],
    "c2g__codaInvoice__c": [
        "Name",
        "c2g__InvoiceDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        "CurrencyIsoCode",
    ],
}


def get_important_fields(object_api_name: str) -> list[str]:
    return IMPORTANT_FIELDS.get(object_api_name, [])


def _first_present(candidates: Iterable[str], cols: set[str]) -> Optional[str]:
    for c in candidates:
        if c in cols:
            return c
    return None


def select_display_columns(
    object_api_name,
    df=None,
    show_all_fields: bool = False,
    *,
    show_ids: bool = False,
) -> list[str]:
    """
    Decide which columns to show in a child table.

    Backwards-compatible with earlier broken signatures:
      - select_display_columns(df)
      - select_display_columns(object_api, df, show_all_fields)

    Rules:
      - If show_all_fields: show all columns.
      - Else: show important fields if present, else fall back to heuristics.
    """
    # Back-compat: called as select_display_columns(df)
    if df is None and hasattr(object_api_name, "columns"):
        _df = object_api_name
        return list(getattr(_df, "columns", []))

    if df is None:
        return []

    cols = list(df.columns)
    if show_all_fields:
        return cols

    colset = set(cols)

    important = [c for c in get_important_fields(str(object_api_name)) if c in colset]
    if important:
        out = important[:]
    else:
        out: list[str] = []

        for key in ("Name", "Subject", "Title", "DocumentTitle"):
            if key in colset and key not in out:
                out.append(key)

        for key in (
            "CloseDate",
            "Amount",
            "StageName",
            "Status",
            "InvoiceDate",
            "TotalAmount",
            "Balance",
            "CurrencyIsoCode",
        ):
            if key in colset and key not in out:
                out.append(key)

        for key in ("AccountId", "OwnerId", "OpportunityId", "ContentDocumentId", "LinkedEntityId"):
            if key in colset and key not in out:
                out.append(key)

        if not out:
            out = cols[:8]

    if show_ids and "Id" in colset and "Id" not in out:
        out.append("Id")

    order_index = {c: i for i, c in enumerate(cols)}
    out = sorted(out, key=lambda c: order_index.get(c, 10_000))
    return out
