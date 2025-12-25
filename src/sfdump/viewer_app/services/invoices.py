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
    """Heuristics: any column name that plausibly stores an Opportunity Id."""
    keys: list[str] = []
    for c in cols:
        lc = c.lower()
        if lc in ("opportunityid", "opportunity__c", "opportunity_id"):
            keys.append(c)
        elif "opportunity" in lc and (
            lc.endswith("id") or lc.endswith("__c") or lc.endswith("_id")
        ):
            keys.append(c)

    # stable order: prefer exact common names
    pref = {"OpportunityId", "Opportunity__c", "opportunityid", "opportunity__c"}
    keys = sorted(keys, key=lambda x: (x not in pref, x))
    return keys


def _select_existing(cols: list[str], wanted: list[str]) -> list[str]:
    return [c for c in wanted if c in cols]


def _looks_like_name_field(field: str) -> bool:
    lf = field.lower()
    return "name" in lf and not lf.endswith("id")


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
) -> tuple[list[dict[str, Any]], str]:
    """
    Best-effort invoice lookup for an Opportunity using:
      1) schema-driven FK scan on likely invoice header tables
      2) bridge fallback via invoice line tables -> invoice header Ids

    Returns: (rows, strategy)
      strategy: "opp-fk" | "line-bridge" | "none" | "no-table"
    """
    header_tables = [
        "c2g__codaInvoice__c",
        "fferpcore__BillingDocument__c",
        "Invoice",
    ]

    line_tables = [
        "c2g__codaInvoiceLineItem__c",
        "fferpcore__BillingDocumentLine__c",
        "InvoiceLine",
    ]

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        # 0) If none of the header tables exist, bail early
        if not any(_table_exists(cur, t) for t in header_tables):
            return ([], "no-table")

        out: list[dict[str, Any]] = []

        # 1) Direct: scan header tables for any Opportunity-ish FK field
        for table in header_tables:
            if not _table_exists(cur, table):
                continue
            cols = _table_columns(cur, table)
            for fk in _candidate_fk_fields(cols):
                out.extend(_fetch_rows_by_fk(cur, table, fk, opportunity_id, limit))

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
            return (uniq, "opp-fk")

        # 2) Bridge: scan line tables for opportunity FK, then map to header Id
        header_id_fields_by_line: dict[str, list[str]] = {
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
                # fallback: guess a header-id-ish column
                for c in cols:
                    lc = c.lower()
                    if ("invoice" in lc or "billingdocument" in lc) and (
                        lc.endswith("__c") or lc.endswith("id")
                    ):
                        header_fk = c
                        break

            if not header_fk:
                continue

            for opp_fk in opp_fks:
                sql = f'SELECT "{header_fk}" FROM "{line_table}" WHERE "{opp_fk}" = ? LIMIT ?'
                cur.execute(sql, (opportunity_id, int(limit)))
                ids = [str(r[0]) for r in cur.fetchall() if r and r[0]]
                if not ids:
                    continue

                for header_table in header_tables:
                    if _table_exists(cur, header_table):
                        collected[header_table].update(ids)

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

        if uniq2:
            return (uniq2, "line-bridge")

        return ([], "none")
    finally:
        conn.close()


def list_invoices_for_account(
    db_path: Path,
    *,
    account_id: str | None = None,
    account_name: str | None = None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], str]:
    """
    Best-effort: list invoices linked to an Account.

    Returns: (rows, strategy)
      strategy: "account-fk" | "none" | "no-table"
    """
    header_tables = [
        "c2g__codaInvoice__c",
        "fferpcore__BillingDocument__c",
        "Invoice",
    ]

    # common account FK names on invoice headers
    candidate_fields = [
        "AccountId",
        "Account__c",
        "c2g__Account__c",
        "c2g__AccountName__c",
        "fferpcore__Account__c",
        "fferpcore__Customer__c",
    ]

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        if not any(_table_exists(cur, t) for t in header_tables):
            return ([], "no-table")

        if not (account_id or account_name):
            return ([], "none")

        out: list[dict[str, Any]] = []

        for table in header_tables:
            if not _table_exists(cur, table):
                continue

            cols = _table_columns(cur, table)
            for fk in [f for f in candidate_fields if f in cols]:
                # Use name only for name-like columns; otherwise use id.
                if _looks_like_name_field(fk):
                    if not account_name:
                        continue
                    val = account_name
                else:
                    if not account_id:
                        continue
                    val = account_id

                out.extend(_fetch_rows_by_fk(cur, table, fk, val, limit))

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

        return (uniq, "account-fk" if uniq else "none")
    finally:
        conn.close()
