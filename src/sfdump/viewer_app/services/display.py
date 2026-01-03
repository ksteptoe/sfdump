from __future__ import annotations

from typing import Iterable, Optional

# Keep this file dependency-light: avoid importing pandas at module import time.


IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": ["Name", "Type", "Industry", "BillingCountry", "BillingCity", "Website", "Phone"],
    "Opportunity": [
        "Name",
        "StageName",
        "Amount",
        "CloseDate",
        "AccountId",
        "Probability",
        "CurrencyIsoCode",
    ],
    "OpportunityLineItem": [
        "OpportunityId",
        "Product2Id",
        "ProductCode",
        "Quantity",
        "UnitPrice",
        "TotalPrice",
        "Description",
    ],
    "Contact": ["Name", "Email", "Phone", "Title", "AccountId", "Department"],
    "ContentDocument": ["Title", "FileType", "ContentSize", "CreatedDate", "LastModifiedDate"],
    "ContentVersion": ["Title", "FileExtension", "ContentSize", "VersionNumber", "CreatedDate"],
    "ContentDocumentLink": ["LinkedEntityId", "ContentDocumentId", "Visibility", "ShareType"],
    "Attachment": ["Name", "ParentId", "ContentType", "BodyLength", "CreatedDate"],
    # Coda/FinancialForce objects
    "c2g__codaInvoice__c": [
        "Name",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__OutstandingValue__c",
        "c2g__AccountName__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaInvoiceLineItem__c": [
        "Name",
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__Quantity__c",
        "c2g__UnitPrice__c",
        "c2g__NetValue__c",
        "c2g__ProductCode__c",
    ],
    "c2g__codaPurchaseInvoice__c": [
        "Name",
        "c2g__Account__c",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__NetTotal__c",
        "c2g__InvoiceTotal__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaPurchaseInvoiceLineItem__c": [
        "Name",
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__Quantity__c",
        "c2g__UnitPrice__c",
        "c2g__NetValue__c",
    ],
    "c2g__codaCompany__c": ["Name", "c2g__CurrencyMode__c", "c2g__BaseCurrency1__c"],
    "c2g__codaPeriod__c": [
        "Name",
        "c2g__StartDate__c",
        "c2g__EndDate__c",
        "c2g__PeriodGroup__c",
        "c2g__Status__c",
    ],
    "c2g__codaAccountingCurrency__c": ["Name", "c2g__DecimalPlaces__c"],
    "c2g__codaBankAccount__c": ["Name", "c2g__BankName__c", "c2g__AccountNumber__c"],
    "c2g__codaGeneralLedgerAccount__c": [
        "Name",
        "c2g__ReportingCode__c",
        "c2g__Type__c",
        "c2g__Balance__c",
    ],
    # Additional Coda/FinancialForce objects
    "c2g__codaCashEntry__c": [
        "Name",
        "c2g__Date__c",
        "c2g__Type__c",
        "c2g__Status__c",
        "c2g__NetValue__c",
        "c2g__PaymentMethod__c",
        "c2g__Reference__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaCreditNote__c": [
        "Name",
        "c2g__CreditNoteDate__c",
        "c2g__DueDate__c",
        "c2g__CreditNoteStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__CreditNoteTotal__c",
        "c2g__NetTotal__c",
        "c2g__OutstandingValue__c",
        "c2g__AccountName__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaJournal__c": [
        "Name",
        "c2g__JournalDate__c",
        "c2g__JournalDescription__c",
        "c2g__JournalStatus__c",
        "c2g__Type__c",
        "c2g__Total__c",
        "c2g__Debits__c",
        "c2g__Credits__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaJournalLineItem__c": [
        "Name",
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__LineType__c",
        "c2g__Value__c",
        "c2g__DebitCredit__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaPayment__c": [
        "Name",
        "c2g__PaymentDate__c",
        "c2g__DueDate__c",
        "c2g__Status__c",
        "c2g__PaymentMethod__c",
        "c2g__PaymentValueTotal__c",
        "c2g__GrossValueTotal__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaPurchaseCreditNote__c": [
        "Name",
        "c2g__CreditNoteDate__c",
        "c2g__DueDate__c",
        "c2g__CreditNoteStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__CreditNoteTotal__c",
        "c2g__NetTotal__c",
        "c2g__OutstandingValue__c",
        "CurrencyIsoCode",
    ],
    "c2g__codaTransaction__c": [
        "Name",
        "c2g__TransactionDate__c",
        "c2g__TransactionType__c",
        "c2g__DocumentNumber__c",
        "c2g__Period__c",
        "c2g__DocumentTotal__c",
        "c2g__Debits__c",
        "c2g__Credits__c",
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
