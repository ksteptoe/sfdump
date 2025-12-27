from __future__ import annotations

from typing import Any

IMPORTANT_FIELDS: dict[str, list[str]] = {
    # Core CRM
    "Account": ["Name", "Type"],
    "Opportunity": ["Name", "StageName", "CloseDate", "Amount"],
    "Contact": ["Name", "Email", "Phone", "Title"],
    # Content / files
    "ContentDocument": ["Title", "LatestPublishedVersionId"],
    "ContentVersion": ["Title", "VersionNumber", "CreatedDate"],
    "ContentDocumentLink": ["DocumentTitle", "ShareType", "Visibility", "LinkedEntityId"],
    # Legacy attachments
    "Attachment": ["Name", "ContentType", "BodyLength", "ParentId"],
    # Finance (generic)
    "Invoice": ["InvoiceNumber", "InvoiceDate", "Status", "TotalAmount", "Balance"],
    "InvoiceLine": ["LineNumber", "ProductName", "Description", "Quantity", "UnitPrice", "Amount"],
    "CreditNote": ["CreditNoteNumber", "CreditNoteDate", "Status", "TotalAmount", "Balance"],
    "CreditNoteLine": ["LineNumber", "Description", "Quantity", "UnitPrice", "Amount"],
    # Coda / FinancialForce (from your export)
    "c2g__codaInvoice__c": [
        "Name",
        "CurrencyIsoCode",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        "c2g__TaxTotal__c",
        "Days_Overdue__c",
        "c2g__AccountName__c",
        "c2g__CompanyReference__c",
    ],
    "c2g__codaInvoiceLineItem__c": [
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__Quantity__c",
        "c2g__UnitPrice__c",
        "c2g__NetValue__c",
        "c2g__TaxValueTotal__c",
        "c2g__ProductCode__c",
        "c2g__ProductReference__c",
    ],
    "OpportunityLineItem": ["Quantity", "UnitPrice", "TotalPrice", "Description"],
}


def get_important_fields(api_name: str) -> list[str]:
    """Return configured 'important' fields for this object, if any."""
    return IMPORTANT_FIELDS.get(api_name, [])


def _drop_id_column(cols: list[str], *, show_ids: bool) -> list[str]:
    if show_ids:
        return cols
    return [c for c in cols if c != "Id"]


def select_display_columns(
    api_name: str, df: Any, show_all: bool, *, show_ids: bool = False
) -> list[str]:
    """
    Decide which columns to show for a given object + DataFrame.

    - If show_all: return all columns (except Id unless show_ids=True).
    - Else: use IMPORTANT_FIELDS if present.
    - Else: fall back to a simple heuristic.
    """
    cols = list(getattr(df, "columns", []))

    if show_all:
        out = cols
        out = _drop_id_column(out, show_ids=show_ids)
        return out

    important = get_important_fields(api_name)
    out: list[str] = [c for c in important if c in cols]

    if not out:
        # Generic heuristic
        for c in ("Name",):
            if c in cols and c not in out:
                out.append(c)
        for c in ("Type", "StageName", "CloseDate", "Amount", "Email", "Title", "Phone"):
            if c in cols and c not in out:
                out.append(c)

    out = _drop_id_column(out, show_ids=show_ids)

    if not out:
        # Fallback: first few columns, still respecting hide-Id default
        out = _drop_id_column(cols, show_ids=show_ids)[:5]

    return out
