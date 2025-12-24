from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]  # (cid, name, type, notnull, dflt_value, pk)


def _candidate_fk_fields(cols: Iterable[str]) -> list[str]:
    """
    Heuristics: any column name that plausibly stores an Opportunity Id.
    """
    keys = []
    for c in cols:
        lc = c.lower()
        if lc in ("opportunityid", "opportunity__c", "opportunity_id"):
            keys.append(c)
        elif "opportunity" in lc and (
            lc.endswith("id") or lc.endswith("__c") or lc.endswith("_id")
        ):
            keys.append(c)
    # stable order: prefer exact common names
    pref = ["OpportunityId", "Opportunity__c", "opportunityid", "opportunity__c"]
    keys = sorted(keys, key=lambda x: (x not in pref, x))
    return keys


def _select_existing(cols: list[str], wanted: list[str]) -> list[str]:
    return [c for c in wanted if c in cols]


def _fetch_rows_by_fk(
    cur: sqlite3.Cursor,
    table: str,
    fk_field: str,
    fk_value: str,
    limit: int,
) -> list[dict[str, Any]]:
    cols = _table_columns(cur, table)
    wanted = [
        "Id",
        "Name",
        "CurrencyIsoCode",
        # Coda invoice fields
        "c2g__InvoiceDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        # FinancialForce-ish
        "fferpcore__InvoiceDate__c",
        "fferpcore__Status__c",
        "fferpcore__Total__c",
        "fferpcore__Outstanding__c",
        # Generic
        "InvoiceDate",
        "Status",
        "TotalAmount",
        "Balance",
    ]
    select_cols = _select_existing(cols, wanted)
    if "Id" not in select_cols:
        return []

    select_sql = ", ".join([f'"{c}"' for c in select_cols])
    sql = f'SELECT {select_sql} FROM "{table}" WHERE "{fk_field}" = ? LIMIT ?'
    cur.execute(sql, (fk_value, int(limit)))
    rows = [dict(zip(select_cols, r, strict=False)) for r in cur.fetchall()]
    for r in rows:
        r["object_type"] = table
        r["_via"] = f"{table}.{fk_field}"
    return rows


def _fetch_invoice_headers_by_ids(
    cur: sqlite3.Cursor,
    table: str,
    ids: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not ids:
        return []
    cols = _table_columns(cur, table)
    wanted = [
        "Id",
        "Name",
        "CurrencyIsoCode",
        "c2g__InvoiceDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        "fferpcore__InvoiceDate__c",
        "fferpcore__Status__c",
        "fferpcore__Total__c",
        "fferpcore__Outstanding__c",
        "InvoiceDate",
        "Status",
        "TotalAmount",
        "Balance",
    ]
    select_cols = _select_existing(cols, wanted)
    if "Id" not in select_cols:
        return []

    ids = ids[: int(limit)]
    ph = ", ".join(["?"] * len(ids))
    select_sql = ", ".join([f'"{c}"' for c in select_cols])
    sql = f'SELECT {select_sql} FROM "{table}" WHERE "Id" IN ({ph})'
    cur.execute(sql, ids)
    rows = [dict(zip(select_cols, r, strict=False)) for r in cur.fetchall()]
    for r in rows:
        r["object_type"] = table
    return rows


def find_invoices_for_opportunity(
    db_path: Path, opportunity_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    """
    Best-effort invoice lookup for an Opportunity using:
      1) schema-driven FK scan on likely invoice header tables
      2) bridge fallback via invoice line tables -> invoice header Ids

    Returns rows with object_type, Id, Name/date/amount fields when present.
    """
    header_tables = [
        "c2g__codaInvoice__c",
        "fferpcore__BillingDocument__c",
        "Invoice",
    ]

    # Known line-item tables that might carry the opportunity FK
    line_tables = [
        "c2g__codaInvoiceLineItem__c",
        "fferpcore__BillingDocumentLine__c",
        "InvoiceLine",
    ]

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        out: list[dict[str, Any]] = []

        # 1) Direct: scan header tables for any Opportunity-ish FK field
        for table in header_tables:
            if not _table_exists(cur, table):
                continue
            cols = _table_columns(cur, table)
            for fk in _candidate_fk_fields(cols):
                out.extend(_fetch_rows_by_fk(cur, table, fk, opportunity_id, limit))

        # If we already found headers, we're done
        if out:
            # De-dupe by (object_type, Id)
            seen: set[tuple[str, str]] = set()
            uniq: list[dict[str, Any]] = []
            for r in out:
                rid = str(r.get("Id") or "")
                ot = str(r.get("object_type") or "")
                key = (ot, rid)
                if rid and ot and key not in seen:
                    seen.add(key)
                    uniq.append(r)
            return uniq

        # 2) Bridge: scan line tables for opportunity FK, then map to header Id
        # Try to discover header-id column names on the line tables.
        header_id_fields_by_line = {
            "c2g__codaInvoiceLineItem__c": ["c2g__Invoice__c", "InvoiceId", "c2g__codaInvoice__c"],
            "fferpcore__BillingDocumentLine__c": [
                "fferpcore__BillingDocument__c",
                "BillingDocumentId",
            ],
            "InvoiceLine": ["InvoiceId", "Invoice__c"],
        }

        collected: dict[str, set[str]] = {t: set() for t in header_tables}

        for line_table in line_tables:
            if not _table_exists(cur, line_table):
                continue
            cols = _table_columns(cur, line_table)

            opp_fks = _candidate_fk_fields(cols)
            if not opp_fks:
                continue

            header_fks = header_id_fields_by_line.get(line_table, [])
            header_fk = next((f for f in header_fks if f in cols), None)
            if not header_fk:
                # also try generic "Invoice" / "BillingDocument" / "Parent" style
                for c in cols:
                    lc = c.lower()
                    if ("invoice" in lc or "billingdocument" in lc) and (
                        lc.endswith("__c") or lc.endswith("id")
                    ):
                        header_fk = c
                        break
            if not header_fk:
                continue

            # Pull header ids from matching lines
            for opp_fk in opp_fks:
                sql = f'SELECT "{header_fk}" FROM "{line_table}" WHERE "{opp_fk}" = ? LIMIT ?'
                cur.execute(sql, (opportunity_id, int(limit)))
                ids = [str(r[0]) for r in cur.fetchall() if r and r[0]]
                if not ids:
                    continue

                # Guess which header table these belong to based on prefix or known mapping
                # If we can't tell, try all header tables.
                for header_table in header_tables:
                    if _table_exists(cur, header_table):
                        for hid in ids:
                            collected[header_table].add(hid)

        bridged: list[dict[str, Any]] = []
        for header_table, ids in collected.items():
            if not ids or not _table_exists(cur, header_table):
                continue
            bridged.extend(_fetch_invoice_headers_by_ids(cur, header_table, sorted(ids), limit))

        # De-dupe
        seen2: set[tuple[str, str]] = set()
        uniq2: list[dict[str, Any]] = []
        for r in bridged:
            rid = str(r.get("Id") or "")
            ot = str(r.get("object_type") or "")
            key = (ot, rid)
            if rid and ot and key not in seen2:
                seen2.add(key)
                uniq2.append(r)
        return uniq2

    finally:
        conn.close()


def list_invoices_for_account(
    db_path: Path, account_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    """Best-effort: list invoices linked to an Account, if your schema exposes an Account FK."""
    header_tables = [
        "c2g__codaInvoice__c",
        "fferpcore__BillingDocument__c",
        "Invoice",
    ]

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        out: list[dict[str, Any]] = []

        # common account FK names on invoice headers
        candidate_fields = [
            "AccountId",
            "Account__c",
            "c2g__Account__c",
            "c2g__AccountName__c",
            "fferpcore__Account__c",
            "fferpcore__Customer__c",
        ]

        for table in header_tables:
            if not _table_exists(cur, table):
                continue
            cols = _table_columns(cur, table)
            for fk in [f for f in candidate_fields if f in cols]:
                out.extend(_fetch_rows_by_fk(cur, table, fk, account_id, limit))

        # de-dupe
        seen: set[tuple[str, str]] = set()
        uniq: list[dict[str, Any]] = []
        for r in out:
            rid = str(r.get("Id") or "")
            ot = str(r.get("object_type") or "")
            key = (ot, rid)
            if rid and ot and key not in seen:
                seen.add(key)
                uniq.append(r)
        return uniq
    finally:
        conn.close()
