from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def find_invoices_for_opportunity(
    db_path: Path, opportunity_id: str, limit: int = 200
) -> list[dict[str, Any]]:
    """
    Best-effort invoice lookup for an Opportunity.

    We try common patterns:
      - c2g__codaInvoice__c: opportunity reference fields if present
      - fferpcore__BillingDocument__c: opportunity reference fields if present
      - generic Invoice: OpportunityId if present

    Returns rows with at least: object_type, Id, Name/number/date/amount where available.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        candidates: list[tuple[str, list[str]]] = [
            # (table, possible opportunity FK fields)
            ("c2g__codaInvoice__c", ["Opportunity__c", "OpportunityId", "c2g__Opportunity__c"]),
            (
                "fferpcore__BillingDocument__c",
                ["Opportunity__c", "OpportunityId", "fferpcore__Opportunity__c"],
            ),
            ("Invoice", ["OpportunityId", "Opportunity__c"]),
        ]

        out: list[dict[str, Any]] = []

        for table, fk_fields in candidates:
            # Skip if table doesn't exist
            try:
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                if not cur.fetchone():
                    continue
            except Exception:
                continue

            # Get columns so we can build a safe query
            cur.execute(f'PRAGMA table_info("{table}")')
            cols = [r["name"] for r in cur.fetchall()]
            fk = next((f for f in fk_fields if f in cols), None)
            if not fk:
                continue

            # Select a friendly set of columns that may exist
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
            select_cols = [c for c in wanted if c in cols]
            if "Id" not in select_cols:
                continue

            select_sql = ", ".join([f'"{c}"' for c in select_cols])
            sql = f'SELECT {select_sql} FROM "{table}" WHERE "{fk}" = ? LIMIT ?'
            cur.execute(sql, (opportunity_id, int(limit)))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["object_type"] = table
            out.extend(rows)

        return out
    finally:
        conn.close()
