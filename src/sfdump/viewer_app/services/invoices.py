from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Tuple


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f'PRAGMA table_info("{table}")')
    return {str(r[1]) for r in cur.fetchall()}


def list_invoices_for_account(
    db_path: Path,
    *,
    account_id: str,
    account_name: str | None = None,
    limit: int = 200,
) -> Tuple[list[dict[str, Any]], str]:
    """
    Best-effort invoice lookup for an Account.

    Returns (rows, strategy) where strategy describes the match used.
    """
    table = "c2g__codaInvoice__c"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cols = _table_columns(conn, table)
        cur = conn.cursor()

        where = None
        params: list[Any] = []
        strategy = "none"

        # 1) Prefer direct AccountId-like reference fields
        direct_fields = ("c2g__Account__c", "AccountId", "c2g__AccountId__c")
        for field in direct_fields:
            if field in cols and account_id:
                where = f'"{field}" = ?'
                params = [account_id]
                strategy = f"id:{field}"
                break

        # 2) Fallback: match by account-name fields
        if where is None and account_name:
            name_fields = ("c2g__AccountName__c", "AccountName")
            for field in name_fields:
                if field in cols:
                    where = f'"{field}" = ?'
                    params = [account_name]
                    strategy = f"name:{field}"
                    break

        if where is None:
            return ([], "none")

        order_date = "c2g__InvoiceDate__c" if "c2g__InvoiceDate__c" in cols else "CreatedDate"

        sql = f"""
        SELECT *
        FROM "{table}"
        WHERE {where}
        ORDER BY COALESCE("{order_date}", "CreatedDate") DESC
        LIMIT ?
        """
        params.append(int(limit))

        cur.execute(sql, params)
        return ([dict(r) for r in cur.fetchall()], strategy)
    except sqlite3.OperationalError:
        return ([], "no-table")
    finally:
        conn.close()
