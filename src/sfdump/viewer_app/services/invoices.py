from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


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
) -> list[dict[str, Any]]:
    """
    Best-effort invoice lookup for an Account.

    We prefer matching by AccountId field if present (e.g. c2g__Account__c),
    otherwise fall back to matching by account name fields if present
    (e.g. c2g__AccountName__c).

    Returns rows from c2g__codaInvoice__c.
    """
    table = "c2g__codaInvoice__c"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cols = _table_columns(conn, table)
        cur = conn.cursor()

        where = None
        params: list[Any] = []

        # 1) Prefer a direct lookup by AccountId-like field
        for field in ("c2g__Account__c", "AccountId", "c2g__AccountId__c"):
            if field in cols:
                where = f'"{field}" = ?'
                params = [account_id]
                break

        # 2) Fallback: match by account name field if present
        if where is None and account_name:
            for field in ("c2g__AccountName__c", "AccountName", "c2g__Account__r.Name"):
                if field in cols:
                    where = f'"{field}" = ?'
                    params = [account_name]
                    break

        if where is None:
            return []

        sql = f"""
        SELECT *
        FROM "{table}"
        WHERE {where}
        ORDER BY
          COALESCE("c2g__InvoiceDate__c", "CreatedDate") DESC
        LIMIT ?
        """
        params.append(int(limit))

        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
