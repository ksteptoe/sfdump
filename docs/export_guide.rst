Salesforce / FinancialForce Export Guide
========================================

This page summarises how to use :command:`sfdump` and :file:`Makefile.export`
to create complete exports of Salesforce and FinancialForce data for
due diligence and off-platform backup.

The export process is driven by the :file:`Makefile.export` at the project root
and relies on the installed :mod:`sfdump` CLI.

Overview
--------

Each export run is stored in a date-stamped directory:

.. code-block:: text

   <BASE_EXPORT_ROOT>/
     export-YYYY-MM-DD/
       files/
       csv/
       meta/

The exact paths are controlled by the Makefile variables:

.. code-block:: make

   BASE_EXPORT_ROOT ?= ./exports
   EXPORT_DATE      ?= $(shell date +%Y-%m-%d)
   EXPORT_ROOT      ?= $(BASE_EXPORT_ROOT)/export-$(EXPORT_DATE)

   CSV_DIR          := $(EXPORT_ROOT)/csv
   FILES_DIR        := $(EXPORT_ROOT)/files
   META_DIR         := $(EXPORT_ROOT)/meta

Using EXPORT_DATE
-----------------

By default, ``EXPORT_DATE`` is set to today's date using ``date +%Y-%m-%d``.
You can override this when calling :command:`make`:

.. code-block:: bash

   make -f Makefile.export EXPORT_DATE=2025-11-15 export-all

or by exporting it in your shell:

.. code-block:: bash

   export EXPORT_DATE=2025-11-15
   make -f Makefile.export export-all

Run ``make -f Makefile.export export-show-config`` to see the effective
``EXPORT_DATE`` and export paths.

Main targets
------------

The most important Make targets are:

- ``export-all`` – run the full export (files, CRM, FinancialForce, HR, meta).
- ``export-files`` – download ``ContentVersion`` and ``Attachment`` records and
  build file indexes for key parent objects (e.g. ``Opportunity``,
  ``SalesforceInvoice``, ``fferpcore__BillingDocument__c``).
- ``export-crm-all`` – export core CRM objects and activities to CSV.
- ``export-ffa`` – export FinancialForce / ERP objects (ff*).
- ``export-hr`` – export HR / employment objects.
- ``export-meta`` – write a list of all sObjects to :file:`meta/all_objects.txt`.

Single-object CSV export
------------------------

To export just a single object, use the ``csv-one`` helper target:

.. code-block:: bash

   make -f Makefile.export EXPORT_DATE=2025-11-15 csv-one OBJ=Account

This invokes the Makefile pattern rule:

.. code-block:: make

   $(CSV_DIR)/%.done:
       @echo "=== Exporting $* to $(CSV_DIR) ==="
       @mkdir -p "$(EXPORT_ROOT)" "$(CSV_DIR)"
       @$(SFDUMP) csv --object $* --out "$(EXPORT_ROOT)" && touch "$@"

which results in a CSV file at:

.. code-block:: text

   <EXPORT_ROOT>/csv/Account.csv

SalesforceInvoice indexing
--------------------------

The file-indexing feature typically uses a SOQL query of the form:

.. code-block:: sql

   SELECT Id, Name FROM <ParentObject>

However, :sobj:`SalesforceInvoice` does not have a ``Name`` field. Instead, we
special-case this object in :mod:`sfdump.command_files` and use
``InvoiceNumber`` as the label:

.. code-block:: sql

   SELECT Id, InvoiceNumber FROM SalesforceInvoice

This allows the files index for ``SalesforceInvoice`` to be built without
errors, while other objects continue to use ``Name``.

See also
--------

The full, step-by-step export guide lives in the Markdown file
``README-export.md`` in the project root. That document covers:

* Directory layout and how exports are organised on disk
* The ``EXPORT_DATE`` mechanism and how to re-run old exports
* ``sfdump files`` usage, including file/attachment indexing
* ``Makefile.export`` targets for CRM, HR and FinancialForce/ERP data
* Troubleshooting common export issues


Opening the full Export README
------------------------------

If you are viewing the HTML docs, you can open or download the full guide here:

:download:`Export README (Markdown) <../README-export.md>`

You can also open it directly from the repository root:

.. code-block:: bash

   # from the project root
   cat README-export.md

   # or open in your editor
   code README-export.md        # VS Code
   pycharm README-export.md     # PyCharm (if configured)


Quick summary of the export flow
--------------------------------

For convenience, here is a high-level summary of how the export process fits
together. See the Markdown README for full details and examples.

1. Choose an export date (optional)

   By default, ``Makefile.export`` uses today's date for the export directory.
   You can override it, for example:

   .. code-block:: bash

      export EXPORT_DATE=2025-11-15   # Git Bash / Linux / macOS

2. Run the full export

   .. code-block:: bash

      make -f Makefile.export export-all

   This will:

   * Download all files and attachments into the date-stamped ``files/`` folder
   * Build helper indexes for key objects (e.g. ``Opportunity``, invoices, POs)
   * Export core CRM, HR and FinancialForce/ERP objects into ``csv/``
   * Write an object list into ``meta/all_objects.txt``

3. Re-run or add objects for a given date

   .. code-block:: bash

      # export an additional object into an existing export
      make -f Makefile.export EXPORT_DATE=2025-11-15 csv-one OBJ=Account

4. Archive if needed

   .. code-block:: bash

      make -f Makefile.export EXPORT_DATE=2025-11-15 export-archive

For more detail, examples and troubleshooting, refer to the full
:download:`Export README (Markdown) <../README-export.md>`.
