from __future__ import annotations

IMPORTANT_FIELDS: dict[str, list[str]] = {
    "Account": ["Id", "Name", "AccountNumber", "Type", "Industry"],
    "Opportunity": ["Id", "Name", "StageName", "CloseDate", "Amount"],
    "Contact": ["Id", "Name", "Email", "Phone", "Title"],
    "ContentDocument": ["Id", "Title", "LatestPublishedVersionId"],
    "ContentVersion": ["Id", "Title", "VersionNumber", "CreatedDate"],
    "ContentDocumentLink": [
        "Id",
        "LinkedEntityId",
        "ContentDocumentId",
        "DocumentTitle",
        "ShareType",
        "Visibility",
    ],
    "Attachment": ["Id", "ParentId", "Name", "ContentType", "BodyLength"],
    # 🧾 Generic finance shapes (kept in case you end up with these names)
    "Invoice": [
        "Id",
        "Name",  # if present
        "InvoiceNumber",
        "InvoiceDate",
        "Status",
        "TotalAmount",
        "Balance",
    ],
    "InvoiceLine": [
        "Id",
        "InvoiceId",
        "LineNumber",
        "ProductName",
        "Description",
        "Quantity",
        "UnitPrice",
        "Amount",
    ],
    "CreditNote": [
        "Id",
        "Name",
        "CreditNoteNumber",
        "CreditNoteDate",
        "Status",
        "TotalAmount",
        "Balance",
    ],
    "CreditNoteLine": [
        "Id",
        "CreditNoteId",
        "LineNumber",
        "Description",
        "Quantity",
        "UnitPrice",
        "Amount",
    ],
    # Concrete Coda / FinancialForce objects from your export
    "c2g__codaInvoice__c": [
        "Id",
        "Name",  # invoice number (SIN001673 etc.)
        "CurrencyIsoCode",
        "c2g__InvoiceDate__c",
        "c2g__DueDate__c",
        "c2g__InvoiceStatus__c",
        "c2g__PaymentStatus__c",
        "c2g__InvoiceTotal__c",
        "c2g__NetTotal__c",
        "c2g__OutstandingValue__c",
        "c2g__TaxTotal__c",
        "Days_Overdue__c",
        "c2g__AccountName__c",
        "c2g__CompanyReference__c",
    ],
    "c2g__codaInvoiceLineItem__c": [
        "Id",
        "Name",
        "c2g__LineNumber__c",
        "c2g__LineDescription__c",
        "c2g__Quantity__c",
        "c2g__UnitPrice__c",
        "c2g__NetValue__c",
        "c2g__TaxRateTotal__c",
        "c2g__TaxValueTotal__c",
        "c2g__ProductCode__c",
        "c2g__ProductReference__c",
    ],
    "OpportunityLineItem": [
        "Id",
        "OpportunityId",
        "PricebookEntryId",
        "Product2Id",
        "Quantity",
        "UnitPrice",
        "TotalPrice",
        "Description",
    ],
}


def important_fields_for(api_name: str) -> list[str]:
    """Return the configured 'important' fields for this object, if any."""
    return IMPORTANT_FIELDS.get(api_name, [])
