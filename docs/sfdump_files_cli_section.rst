The ``sfdump files`` command downloads Salesforce files and attachments and can
optionally build CSV indexes that relate files back to their parent records.

Basic usage::

    sfdump files --out PATH/TO/files

By default this will:

* Download the latest ``ContentVersion`` records ("Files")
* Download legacy ``Attachment`` records

You can disable each kind independently::

    sfdump files --out PATH/TO/files --no-content       # only Attachment
    sfdump files --out PATH/TO/files --no-attachments   # only ContentVersion

**Indexing**

To build CSV indexes that map parent sObjects (for example, ``Opportunity``) to
their related files and attachments, use ``--index-by``::

    sfdump files \
      --out PATH/TO/files \
      --index-by Opportunity \
      --index-by Account

This creates CSVs under ``PATH/TO/files/links/``, for example::

    PATH/TO/files/links/Opportunity_files_index.csv

Each row links a record (e.g. an ``Opportunity``) to a downloaded file or
attachment.

**Index-only mode**

When debugging the indexing logic you often do not want to re-download tens of
thousands of files. For this use case there is an ``--index-only`` flag::

    # Rebuild indexes without downloading
    sfdump files \
      --out PATH/TO/files \
      --index-by Opportunity \
      --index-by SalesforceInvoice \
      --index-only

In this mode:

* No ``ContentVersion`` or ``Attachment`` bodies are downloaded.
* The command only queries the parent objects and ``ContentDocumentLink``
  relations and rewrites the index CSVs in ``PATH/TO/files/links``.

Important:

* You must have run at least one full download previously so that the underlying
  files are already present on disk.
* ``--index-only`` is mutually exclusive with ``--estimate-only``.

**Special label fields**

Most objects have a ``Name`` field that can be used as a human-readable label in
the index. Some FinancialForce objects do not. To handle this, the indexer uses
a small mapping in the code (for example ``INDEX_LABEL_FIELDS``) so that specific
objects use a different field::

    INDEX_LABEL_FIELDS = {
        "SalesforceInvoice": "InvoiceNumber",
        # e.g.
        # "ffps_po__PurchaseOrder__c": "Name__c",
    }

If no special mapping is defined, ``Name`` is used by default.
