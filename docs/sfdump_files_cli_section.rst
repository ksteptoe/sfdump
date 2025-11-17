.. _sfdump_files_cli:

sfdump files
============

The ``files`` subcommand downloads Salesforce files and attachments and can
optionally build CSV indexes that relate files back to their parent records.

Basic usage
-----------

The simplest usage is:

.. code-block:: console

   sfdump files --out /path/to/files

By default this will:

* Download the latest ``ContentVersion`` records (“Files”)
* Download legacy ``Attachment`` records

You can disable each kind independently:

.. code-block:: console

   sfdump files --out /path/to/files --no-content       # only Attachment
   sfdump files --out /path/to/files --no-attachments   # only ContentVersion

Full syntax:

.. code-block:: console

   sfdump files --out /path/to/files \
       [--no-content] [--no-attachments] \
       [--content-where "<extra AND filter>"] \
       [--attachments-where "<WHERE>"] \
       [--max-workers N] \
       [--index-by SOBJECT] [--index-by SOBJECT] [...]

Key options:

- ``--no-content``: skip ``ContentVersion`` / ``ContentDocument`` files.
- ``--no-attachments``: skip legacy ``Attachment`` records.
- ``--content-where``: extra ``AND`` filter for ``ContentVersion``.
- ``--attachments-where``: ``WHERE`` clause for ``Attachment``.
- ``--max-workers``: number of parallel download workers.
- ``--index-by``: build per-object file link indexes under
  ``files/links`` for the given sObject.

Indexing
--------

To build CSV indexes that map parent sObjects (for example, ``Opportunity``) to
their related files and attachments, use ``--index-by``:

.. code-block:: console

   sfdump files \
     --out /path/to/files \
     --index-by Opportunity \
     --index-by Account \
     --index-by fferpcore__BillingDocument__c

This produces CSVs such as:

- ``files/links/Opportunity_files_index.csv``
- ``files/links/Account_files_index.csv``

Each row links a parent record (Opportunity, Account, etc.) to the related
Attachment or File, including basic metadata (file name, extension, etc.).

Index-only mode
---------------

When debugging the indexing logic you often do not want to re-download tens of
thousands of files. For this use case there is an ``--index-only`` flag:

.. code-block:: console

   # Rebuild indexes without downloading
   sfdump files \
     --out /path/to/files \
     --index-by Opportunity \
     --index-by SalesforceInvoice \
     --index-only

In this mode:

* No ``ContentVersion`` or ``Attachment`` bodies are downloaded.
* The command only queries the parent objects and ``ContentDocumentLink``
  relations and rewrites the index CSVs in ``/path/to/files/links``.

Important:

* You must have run at least one full download previously so that the underlying
  files are already present on disk.
* ``--index-only`` is mutually exclusive with ``--estimate-only``.

Special label fields
--------------------

Most objects have a ``Name`` field that can be used as a human-readable label in
the index. Some FinancialForce objects do not. To handle this, the indexer uses
a small mapping in the code (for example ``INDEX_LABEL_FIELDS``) so that specific
objects use a different field:

.. code-block:: python

   INDEX_LABEL_FIELDS = {
       "SalesforceInvoice": "InvoiceNumber",
       # e.g.
       # "ffps_po__PurchaseOrder__c": "Name__c",
   }

If no special mapping is defined, ``Name`` is used by default.

Related command: sfdump docs-index
----------------------------------

The per-object indexes produced by ``sfdump files --index-by`` are
designed to be combined into a single *master documents index* for each
export.

The companion command :ref:`sfdump_docs_index_cli`:

.. code-block:: console

   sfdump docs-index --export-root /path/to/export-YYYY-MM-DD

reads:

- Per-object ``*_files_index.csv`` under ``files/links``
- ``attachments.csv`` and ``content_versions.csv`` under ``files/links``
- ``Account.csv`` and ``Opportunity.csv`` under ``csv``

and writes:

- ``meta/master_documents_index.csv``

This consolidated CSV can be loaded into Excel, Power BI, or a small
web UI to provide a searchable document browser that continues to work
after Salesforce has been switched off.

.. _sfdump_docs_index_cli:

sfdump docs-index
=================

.. code-block:: console

   sfdump docs-index --export-root /path/to/export-YYYY-MM-DD

Build a consolidated ``meta/master_documents_index.csv`` for a single
SFdump export run.

This command reads:

- Per-object ``*_files_index.csv`` under ``files/links``
- ``attachments.csv`` and ``content_versions.csv`` under ``files/links``
- ``Account.csv`` and ``Opportunity.csv`` under ``csv``

and writes:

- ``meta/master_documents_index.csv``

The resulting CSV is intended to be used by downstream tools (Excel,
Power BI, or a small UI) to provide a searchable document browser that
continues to work after Salesforce has been switched off.
