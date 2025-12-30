from __future__ import annotations

from typing import Iterable

import pandas as pd

# A small, opinionated set of "important" fields for common objects.
# Falls back to heuristics if object not present.
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
        "CreatedDate",
        "LastModifiedDate",
        "Id",
    ],
    "Opportunity": [
        "Name",
        "StageName",
        "Amount",
        "CloseDate",
        "AccountId",
        "OwnerId",
        "Probability",
        "CreatedDate",
        "LastModifiedDate",
        "Id",
    ],
    "Contact": [
        "Name",
        "Email",
        "Phone",
        "AccountId",
        "Title",
        "OwnerId",
        "CreatedDate",
        "LastModifiedDate",
        "Id",
    ],
    "ContentDocumentLink": [
        "ContentDocumentId",
        "LinkedEntityId",
        "ShareType",
        "Visibility",
        "Id",
    ],
}


def get_important_fields(api_name: str) -> list[str]:
    """
    Return a preferred field order for an object.
    """
    return IMPORTANT_FIELDS.get(
        api_name, ["Name", "Title", "Subject", "CreatedDate", "LastModifiedDate", "Id"]
    )


def _dedupe(seq: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in seq:
        if s and s not in seen:
            out.append(s)
            seen.add(s)
    return out


def select_display_columns(
    api_name: str | pd.DataFrame,
    df: pd.DataFrame | None = None,
    show_all_fields: bool = False,
    *,
    max_cols: int = 14,
) -> list[str]:
    """
    Choose a reasonable subset of columns to display in child tables.

    Supports two call styles:
      - select_display_columns(api_name, df, show_all_fields)
      - select_display_columns(df)  (back-compat)
    """
    if isinstance(api_name, pd.DataFrame):
        # back-compat: first arg was df
        df = api_name
        api = ""
        # show_all = bool(df is not None and False)  # keep lint happy
        # caller didn't supply show_all_fields in this mode
        show_all_fields = False
    else:
        api = api_name

    if df is None or df.empty:
        return []

    cols = list(df.columns)

    if show_all_fields:
        return cols

    preferred = get_important_fields(api)

    # Heuristics: keep Id-ish things and a couple of obvious labels
    always = [c for c in cols if c.lower() in {"id", "name", "title", "subject"}]
    preferred_present = [c for c in preferred if c in cols]

    # plus: common foreign keys (AccountId, OpportunityId, etc.)
    fk = [c for c in cols if c.endswith("Id") and c != "Id"]

    chosen = _dedupe(always + preferred_present + fk)

    # If still too few, add remaining columns up to max_cols
    if len(chosen) < min(max_cols, len(cols)):
        for c in cols:
            if c not in chosen:
                chosen.append(c)
            if len(chosen) >= max_cols:
                break

    return chosen[:max_cols]
