from __future__ import annotations

from typing import Any, Dict, List, Sequence

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


def get_important_fields(api_name: str) -> List[str]:
    """
    Fields to prefer when building labels / compact displays.
    Keep conservative: only include fields that tend to exist.
    """
    base = ["Name", "Subject", "Title", "DocumentTitle"]
    extra: Dict[str, List[str]] = {
        "Opportunity": ["StageName", "Amount", "CloseDate"],
        "Account": ["BillingCountry", "BillingCity"],
        "Contact": ["Email"],
    }
    return extra.get(api_name, []) + base


def _cols_from_any(data: Any) -> List[str]:
    # pandas DataFrame
    if pd is not None:
        try:
            if isinstance(data, pd.DataFrame):
                return [str(c) for c in list(data.columns)]
        except Exception:
            pass

    # list[dict]
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return [str(c) for c in list(data[0].keys())]

    # generic
    return []


def _default_cols(cols: Sequence[str], *, show_all_fields: bool, show_ids: bool) -> List[str]:
    cols = list(cols)
    if not cols:
        return []

    # Id-ish fields
    id_cols = [c for c in cols if c.lower() == "id" or c.lower().endswith("id")]
    non_id = [c for c in cols if c not in id_cols]

    if not show_ids:
        non_id = [c for c in non_id if not (c.lower() == "id" or c.lower().endswith("id"))]
        id_cols = []

    if show_all_fields:
        return id_cols + non_id

    preferred = [
        "Name",
        "Title",
        "Subject",
        "StageName",
        "Amount",
        "CloseDate",
        "Email",
        "CreatedDate",
    ]
    chosen: List[str] = []

    if show_ids and "Id" in cols:
        chosen.append("Id")

    for c in preferred:
        if c in cols and c not in chosen:
            chosen.append(c)

    # Fallback: first N cols (after Id handling)
    if not chosen:
        chosen = (id_cols + non_id)[:12]

    return chosen


def select_display_columns(*args: Any, **kwargs: Any) -> List[str]:
    """
    Backwards-compatible helper.

    Supports BOTH call shapes:

      1) OLD (used by db_app.py):
         select_display_columns(api_name: str, df_or_rows, show_all_fields: bool)

      2) NEW:
         select_display_columns(rows_or_df, show_all_fields=..., show_ids=...)

    Returns a list of column names to display.
    """
    show_ids = bool(kwargs.get("show_ids", False))

    # OLD signature: (api_name, data, show_all_fields)
    if len(args) >= 3 and isinstance(args[0], str) and isinstance(args[2], (bool, int)):
        _api_name = args[0]  # unused currently but kept for compatibility
        data = args[1]
        show_all_fields = bool(args[2])
        cols = _cols_from_any(data)
        return _default_cols(cols, show_all_fields=show_all_fields, show_ids=show_ids)

    # NEW signature: (data, *, show_all_fields=..., show_ids=...)
    if len(args) >= 1:
        data = args[0]
        show_all_fields = bool(kwargs.get("show_all_fields", False))
        cols = _cols_from_any(data)
        return _default_cols(cols, show_all_fields=show_all_fields, show_ids=show_ids)

    return []
