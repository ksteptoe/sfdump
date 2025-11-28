
===============================
SF Dump: File Indexing Architecture
===============================

Overview
========

This document describes how ``sfdump`` retrieves, indexes, and links Salesforce
files and attachments to their parent business objects.  It provides:

- A model of how Salesforce stores files
- An ASCII entity-relationship diagram
- Details of the indexing CSVs generated during export
- A technical section for developers explaining the Python code paths

This file is written in portable, Sphinx-compatible reStructuredText.


1. Salesforce File Storage Model
================================

Salesforce represents files using two different systems:

Legacy Attachments
------------------

The older ``Attachment`` object stores file data directly on the record.

Fields include:

- ``Id``
- ``ParentId``
- ``Name``
- ``Body`` (binary data)

Relationship:

::

   Attachment.ParentId  -->  <any Salesforce record>


Modern Files (ContentVersion / ContentDocument)
-----------------------------------------------

Modern Salesforce uses a three-object model:

::

   ContentDocument  (logical file)
       |
       | (1-to-many)
       v
   ContentVersion  (specific version of file)
       |
       | (many-to-many through ContentDocumentLink)
       v
   ContentDocumentLink  (links file to parent objects)

Each uploaded file may have multiple versions and may be linked to
multiple records.


2. ASCII Entity Relationship Diagram
====================================

::

   +------------------+         +------------------+
   |  Sales Objects   |         |  User            |
   | (Account,        |         | (CreatedBy)      |
   |  Opportunity,    |         +------------------+
   |  Invoice__c...)  |
   +--------+---------+
            ^
            | ParentId (Attachment)
            |
   +--------+---------+
   |   Attachment     |
   | Id, ParentId     |
   | Name, Body       |
   +------------------+

   Modern Files:

   +------------------+        +------------------+
   | ContentDocument  |<-------| ContentVersion   |
   | Id               | 1..n   | Id               |
   | LatestVersionId  |        | ContentDocument  |
   +------------------+        | VersionNumber    |
                               | Title, FileType  |
                               | VersionData      |
                               +------------------+
                                           |
                                           | n..n via ContentDocumentLink
                                           v
                                  +-------------------------+
                                  | ContentDocumentLink     |
                                  | ContentDocumentId       |
                                  | LinkedEntityId (parent) |
                                  | ShareType               |
                                  +-------------------------+


3. Parent Objects Used for Indexing
===================================

``sfdump`` indexes content files and attachments against the following
Salesforce objects (from ``Makefile`` selection):

::

   Opportunity
   Account
   Project__c
   Invoices__c
   SalesforceInvoice
   SalesforceContract
   SalesforceQuote
   fferpcore__BillingDocument__c
   ffc_statex__StatementAccount__c
   ffps_po__PurchaseOrder__c
   ffps_po__GoodsReceiptNote__c
   ffvat__VatReturn__c
   c2g__codaInvoice__c
   c2g__codaCreditNote__c
   c2g__codaPurchaseInvoice__c
   c2g__codaPurchaseCreditNote__c
   pse__Proj__c
   pse__Assignment__c
   pse__Timecard__c
   pse__Expense_Report__c
   pse__Vendor_Invoice__c
   Engineer__c
   JobApplication__c
   HR_Activity__c
   Salary_History__c


4. Indexing Pipeline Overview
=============================

The pipeline is implemented primarily in:

- ``files.dump_content_versions``
- ``files.dump_attachments``
- ``api.SalesforceAPI``
- ``utils.ensure_dir``

Summary of the process:

1. Query Salesforce for ``ContentVersion`` records
2. Download file binaries (``VersionData``)
3. Resolve parent links via ``ContentDocumentLink``
4. Query label fields for parent objects
5. Write indexes as ``CSV`` metadata tables


5. Index CSV Files
==================

index_content_files.csv
-----------------------

One row per (file, parent object) association.

Fields include:

- ``file_id``
- ``file_path``
- ``content_document_id``
- ``content_version_id``
- ``parent_id``
- ``parent_object``
- ``parent_label_field``
- ``parent_label_value``
- ``title``
- ``file_type``
- ``created_by``
- ``created_date``


index_attachments.csv
---------------------

Fields include:

- ``attachment_id``
- ``file_path``
- ``parent_id``
- ``parent_object``
- ``parent_label_value``
- ``name``
- ``created_by``
- ``created_date``


6. Developer Guide
==================

This section explains the relevant Python functions and modules used in
the indexing pipeline.


6.1 Module: files.py
--------------------

dump_content_versions(api, outdir, parents)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Responsible for:

- Querying Salesforce for ``ContentVersion`` records
- Downloading file binaries via ``VersionData``
- Resolving parent records through ``ContentDocumentLink``
- Constructing index rows
- Saving each file to disk

Output:

- ``<outdir>/files/<ContentVersionId>_<Title>.<ext>``
- ``index_content_files.csv`` (combined later)


dump_attachments(api, outdir, parents)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Handles legacy ``Attachment`` objects.

Responsibilities:

- Query ``Attachment`` where ``ParentId`` matches known parent objects
- Download ``Body`` as binary
- Save to ``attachments`` directory
- Produce index entries


6.2 Module: api.py
------------------

SalesforceAPI
~~~~~~~~~~~~~

Wrapper around Salesforce REST API or Bulk API.

Key methods used:

- ``query(soql)`` – fetches records
- ``download_content(version_id)`` – fetches binary file data


SFConfig
~~~~~~~~

Loads credentials (environment variables or ``.env``).


6.3 Module: utils.py
--------------------

ensure_dir(path)
~~~~~~~~~~~~~~~~

Creates directories safely before downloads occur.


6.4 How Label Fields Are Resolved
---------------------------------

The dictionary ``INDEX_LABEL_FIELDS`` determines which human-readable
field should appear in the index for each parent object.

Example:

::

   INDEX_LABEL_FIELDS = {
       "SalesforceInvoice": "InvoiceNumber",
       "SalesforceContract": "BillingCompany",
   }


Other objects default to ``Name``.


7. Example Queries (Post-Export)
================================

Python:

.. code-block:: python

   import pandas as pd
   idx = pd.read_csv("index_content_files.csv")
   invoice_files = idx[idx.parent_object == "SalesforceInvoice"]


Shell:

::

   grep "SalesforceInvoice" index_content_files.csv


8. Summary
==========

The indexing system provides a durable, searchable mapping from all
Salesforce files back to their associated business objects including
invoices, HR records, opportunities, and projects.

This allows long-term auditability even after Salesforce access expires.
