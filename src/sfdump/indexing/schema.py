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
    "Invoice": SFObject(
        api_name="Invoice",
        label="Invoice",
        table_name="invoice",
    ),
    "InvoiceLine": SFObject(
        api_name="InvoiceLine",
        label="Invoice Line",
        table_name="invoice_line",
    ),
    "CreditNote": SFObject(
        api_name="CreditNote",
        label="Credit Note",
        table_name="credit_note",
    ),
    "CreditNoteLine": SFObject(
        api_name="CreditNoteLine",
        label="Credit Note Line",
        table_name="credit_note_line",
    ),
    "c2g__codaInvoice__c": SFObject(
        api_name="c2g__codaInvoice__c",
        label="Coda Sales Invoice",
        table_name="c2g__codaInvoice__c",
    ),
    "c2g__codaInvoiceLineItem__c": SFObject(
        api_name="c2g__codaInvoiceLineItem__c",
        label="Coda Invoice Line Item",
        table_name="c2g__codaInvoiceLineItem__c",
    ),
    "OpportunityLineItem": SFObject(
        api_name="OpportunityLineItem",
        label="Opportunity Line Item",
        table_name="OpportunityLineItem",
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
    SFRelationship(
        name="Account_Invoice",
        parent="Account",
        child="Invoice",
        child_field="AccountId",
    ),
    SFRelationship(
        name="Invoice_InvoiceLine",
        parent="Invoice",
        child="InvoiceLine",
        child_field="InvoiceId",
    ),
    SFRelationship(
        name="Account_CreditNote",
        parent="Account",
        child="CreditNote",
        child_field="AccountId",
    ),
    SFRelationship(
        name="CreditNote_CreditNoteLine",
        parent="CreditNote",
        child="CreditNoteLine",
        child_field="CreditNoteId",
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
