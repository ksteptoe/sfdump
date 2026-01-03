"""Central description of Salesforce objects and their relationships.
This module is deliberately *data-only* (no I/O) so it can be used by:
- index builders
- SQL/SQLite schema generators
- viewers / UIs that want to navigate objects and relationships
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class SFObject:
    """Represents a Salesforce object that we export.

    Attributes
    ----------
    api_name:
        The Salesforce API name (e.g. "Account", "ContentDocument").
    label:
        A human-friendly label for UIs.
    table_name:
        The name we use for CSV/SQL tables (typically lower_snake_case).
    id_field:
        The primary key field on this object (defaults to "Id").
    """

    api_name: str
    label: str
    table_name: str
    id_field: str = "Id"


@dataclass(frozen=True)
class SFRelationship:
    """Represents a parent/child relationship between two SFObjects.

    This is intentionally simple: one child field pointing at the parent's Id.

    Attributes
    ----------
    name:
        A unique name for this relationship (for debugging / UIs).
    parent:
        Parent object's API name (e.g. "Account").
    child:
        Child object's API name (e.g. "Opportunity").
    child_field:
        Field on the child that references the parent's Id
        (e.g. "AccountId", "ContentDocumentId").
    cardinality:
        Logical cardinality from parent to child.
        Currently only "one-to-many" is used but we keep it explicit.
    """

    name: str
    parent: str
    child: str
    child_field: str
    cardinality: str = "one-to-many"


# ---------------------------------------------------------------------------
# Object registry
# ---------------------------------------------------------------------------

OBJECTS: Dict[str, SFObject] = {
    # Core business objects (extend as needed)
    "Account": SFObject(
        api_name="Account",
        label="Account",
        table_name="account",
    ),
    "Opportunity": SFObject(
        api_name="Opportunity",
        label="Opportunity",
        table_name="opportunity",
    ),
    "OpportunityLineItem": SFObject(
        api_name="OpportunityLineItem",
        label="Opportunity Line Item",
        table_name="OpportunityLineItem",
    ),
    "Contact": SFObject(
        api_name="Contact",
        label="Contact",
        table_name="contact",
    ),
    # Files / attachments
    "ContentDocument": SFObject(
        api_name="ContentDocument",
        label="Content Document",
        table_name="content_document",
    ),
    "ContentVersion": SFObject(
        api_name="ContentVersion",
        label="Content Version",
        table_name="content_version",
    ),
    "ContentDocumentLink": SFObject(
        api_name="ContentDocumentLink",
        label="Content Document Link",
        table_name="content_document_link",
    ),
    "Attachment": SFObject(
        api_name="Attachment",
        label="Legacy Attachment",
        table_name="attachment",
    ),
    # Finance objects
    "c2g__codaInvoice__c": SFObject(
        api_name="c2g__codaInvoice__c",
        label="Invoice",
        table_name="c2g__codaInvoice__c",
    ),
    "c2g__codaInvoiceLineItem__c": SFObject(
        api_name="c2g__codaInvoiceLineItem__c",
        label="Invoice Line Item",
        table_name="c2g__codaInvoiceLineItem__c",
    ),
    "c2g__codaTransaction__c": SFObject(
        api_name="c2g__codaTransaction__c",
        label="Transaction",
        table_name="c2g__codaTransaction__c",
    ),
    "c2g__codaJournal__c": SFObject(
        api_name="c2g__codaJournal__c",
        label="Journal",
        table_name="c2g__codaJournal__c",
    ),
    "c2g__codaJournalLineItem__c": SFObject(
        api_name="c2g__codaJournalLineItem__c",
        label="Journal Line Item",
        table_name="c2g__codaJournalLineItem__c",
    ),
    "c2g__codaPurchaseInvoice__c": SFObject(
        api_name="c2g__codaPurchaseInvoice__c",
        label="Purchase Invoice",
        table_name="c2g__codaPurchaseInvoice__c",
    ),
    # Finance supporting objects
    "c2g__codaCompany__c": SFObject(
        api_name="c2g__codaCompany__c",
        label="Company",
        table_name="c2g__codaCompany__c",
    ),
    "c2g__codaPeriod__c": SFObject(
        api_name="c2g__codaPeriod__c",
        label="Period",
        table_name="c2g__codaPeriod__c",
    ),
    "c2g__codaAccountingCurrency__c": SFObject(
        api_name="c2g__codaAccountingCurrency__c",
        label="Accounting Currency",
        table_name="c2g__codaAccountingCurrency__c",
    ),
    "c2g__codaBankAccount__c": SFObject(
        api_name="c2g__codaBankAccount__c",
        label="Bank Account",
        table_name="c2g__codaBankAccount__c",
    ),
    "c2g__codaGeneralLedgerAccount__c": SFObject(
        api_name="c2g__codaGeneralLedgerAccount__c",
        label="General Ledger Account",
        table_name="c2g__codaGeneralLedgerAccount__c",
    ),
    # Add further exported objects here as we need them
}


# ---------------------------------------------------------------------------
# Relationship registry
# ---------------------------------------------------------------------------

RELATIONSHIPS: List[SFRelationship] = [
    # Core business object relationships
    SFRelationship(
        name="Account_Opportunity",
        parent="Account",
        child="Opportunity",
        child_field="AccountId",
    ),
    SFRelationship(
        name="Account_Contact",
        parent="Account",
        child="Contact",
        child_field="AccountId",
    ),
    SFRelationship(
        name="Opportunity_OpportunityLineItem",
        parent="Opportunity",
        child="OpportunityLineItem",
        child_field="OpportunityId",
    ),
    # Files / attachments relationships
    SFRelationship(
        name="ContentDocument_ContentVersion",
        parent="ContentDocument",
        child="ContentVersion",
        child_field="ContentDocumentId",
    ),
    SFRelationship(
        name="Parent_ContentDocumentLink",
        parent="*",
        # parent="*" means polymorphic parent: Account, Opportunity, Case, etc.
        child="ContentDocumentLink",
        child_field="LinkedEntityId",
    ),
    SFRelationship(
        name="ContentDocumentLink_ContentDocument",
        parent="ContentDocument",
        child="ContentDocumentLink",
        child_field="ContentDocumentId",
    ),
    SFRelationship(
        name="Parent_Attachment",
        parent="*",
        child="Attachment",
        child_field="ParentId",
    ),
    # Finance relationships
    # Invoice Line Item and Invoice
    SFRelationship(
        name="InvoiceLineItem",
        parent="c2g__codaInvoice__c",
        child="c2g__codaInvoiceLineItem__c",
        child_field="c2g__Invoice__c",
    ),
    # Account -> Invoice (Invoice has c2g__Account__c)
    SFRelationship(
        name="Account_CodaInvoice",
        parent="Account",
        child="c2g__codaInvoice__c",
        child_field="c2g__Account__c",
    ),
    # Opportunity -> Invoice (Invoice has c2g__Opportunity__c)
    SFRelationship(
        name="Opportunity_CodaInvoice",
        parent="Opportunity",
        child="c2g__codaInvoice__c",
        child_field="c2g__Opportunity__c",
    ),
    # Transaction -> Invoice (Invoice has c2g__Transaction__c)
    SFRelationship(
        name="CodaTransaction_CodaInvoice",
        parent="c2g__codaTransaction__c",
        child="c2g__codaInvoice__c",
        child_field="c2g__Transaction__c",
    ),
    # Company -> Invoice (Invoice has c2g__OwnerCompany__c)
    SFRelationship(
        name="CodaCompany_CodaInvoice",
        parent="c2g__codaCompany__c",
        child="c2g__codaInvoice__c",
        child_field="c2g__OwnerCompany__c",
    ),
    # Period -> Invoice (Invoice has c2g__Period__c)
    SFRelationship(
        name="CodaPeriod_CodaInvoice",
        parent="c2g__codaPeriod__c",
        child="c2g__codaInvoice__c",
        child_field="c2g__Period__c",
    ),
    # Currency -> Invoice (Invoice has c2g__InvoiceCurrency__c)
    SFRelationship(
        name="CodaAccountingCurrency_CodaInvoice",
        parent="c2g__codaAccountingCurrency__c",
        child="c2g__codaInvoice__c",
        child_field="c2g__InvoiceCurrency__c",
    ),
    # BankAccount -> Invoice (Invoice has Bank_Account__c)
    SFRelationship(
        name="CodaBankAccount_CodaInvoice",
        parent="c2g__codaBankAccount__c",
        child="c2g__codaInvoice__c",
        child_field="Bank_Account__c",
    ),
    # GeneralLedgerAccount -> Invoice (Invoice has c2g__GeneralLedgerAccount__c)
    SFRelationship(
        name="CodaGeneralLedgerAccount_CodaInvoice",
        parent="c2g__codaGeneralLedgerAccount__c",
        child="c2g__codaInvoice__c",
        child_field="c2g__GeneralLedgerAccount__c",
    ),
    # Journal -> Transaction (Transaction has c2g__Journal__c)
    SFRelationship(
        name="CodaJournal_CodaTransaction",
        parent="c2g__codaJournal__c",
        child="c2g__codaTransaction__c",
        child_field="c2g__Journal__c",
    ),
    # Journal -> Journal Line Items
    SFRelationship(
        name="CodaJournal_JournalLineItem",
        parent="c2g__codaJournal__c",
        child="c2g__codaJournalLineItem__c",
        child_field="c2g__Journal__c",
    ),
    # Company -> Journal (Journal has c2g__OwnerCompany__c)
    SFRelationship(
        name="CodaCompany_CodaJournal",
        parent="c2g__codaCompany__c",
        child="c2g__codaJournal__c",
        child_field="c2g__OwnerCompany__c",
    ),
    # Period -> Journal (Journal has c2g__Period__c)
    SFRelationship(
        name="CodaPeriod_CodaJournal",
        parent="c2g__codaPeriod__c",
        child="c2g__codaJournal__c",
        child_field="c2g__Period__c",
    ),
    # Currency -> Journal (Journal has c2g__JournalCurrency__c)
    SFRelationship(
        name="CodaAccountingCurrency_CodaJournal",
        parent="c2g__codaAccountingCurrency__c",
        child="c2g__codaJournal__c",
        child_field="c2g__JournalCurrency__c",
    ),
    # Purchase Invoice relationships
    # Account -> PurchaseInvoice (PurchaseInvoice has c2g__Account__c)
    SFRelationship(
        name="Account_CodaPurchaseInvoice",
        parent="Account",
        child="c2g__codaPurchaseInvoice__c",
        child_field="c2g__Account__c",
    ),
    # Company -> PurchaseInvoice (PurchaseInvoice has c2g__OwnerCompany__c)
    SFRelationship(
        name="CodaCompany_CodaPurchaseInvoice",
        parent="c2g__codaCompany__c",
        child="c2g__codaPurchaseInvoice__c",
        child_field="c2g__OwnerCompany__c",
    ),
    # Period -> PurchaseInvoice (PurchaseInvoice has c2g__Period__c)
    SFRelationship(
        name="CodaPeriod_CodaPurchaseInvoice",
        parent="c2g__codaPeriod__c",
        child="c2g__codaPurchaseInvoice__c",
        child_field="c2g__Period__c",
    ),
    # Currency -> PurchaseInvoice (PurchaseInvoice has c2g__InvoiceCurrency__c)
    SFRelationship(
        name="CodaAccountingCurrency_CodaPurchaseInvoice",
        parent="c2g__codaAccountingCurrency__c",
        child="c2g__codaPurchaseInvoice__c",
        child_field="c2g__InvoiceCurrency__c",
    ),
    # Transaction -> PurchaseInvoice (PurchaseInvoice has c2g__Transaction__c)
    SFRelationship(
        name="CodaTransaction_CodaPurchaseInvoice",
        parent="c2g__codaTransaction__c",
        child="c2g__codaPurchaseInvoice__c",
        child_field="c2g__Transaction__c",
    ),
]


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_object(api_name: str) -> SFObject:
    """Return the SFObject definition for the given API name.

    Raises KeyError if the object is unknown.
    """
    return OBJECTS[api_name]


def iter_objects() -> Iterable[SFObject]:
    """Iterate over all known SFObjects."""
    return OBJECTS.values()


def children_of(parent_api_name: str) -> List[SFRelationship]:
    """Return relationships where the given object is the parent.

    A relationship with parent="*" is considered to apply to any parent type,
    and will be included for all calls to this function.
    """
    result: List[SFRelationship] = []
    for rel in RELATIONSHIPS:
        if rel.parent == parent_api_name or rel.parent == "*":
            result.append(rel)
    return result


def parents_of(child_api_name: str) -> List[SFRelationship]:
    """Return relationships where the given object is the child."""
    return [rel for rel in RELATIONSHIPS if rel.child == child_api_name]
