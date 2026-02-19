======
sfdump
======

Salesforce data export and archival tool. Bulk downloads Attachments,
ContentVersions, CSV object data, and invoice PDFs with verification,
retry mechanisms, a searchable SQLite database, and a Streamlit web viewer.

Built for organisations whose Salesforce licences may expire -- provides
confidence that everything has been captured and can be browsed offline.

Features
========

- **Full data export** -- 44 essential Salesforce objects exported to CSV
- **File downloads** -- Attachments (legacy) and ContentVersions with SHA-256 verification
- **Invoice PDFs** -- bulk download via deployed Apex REST endpoint (``sf sins``)
- **SQLite database** -- queryable offline database built from CSV exports
- **Streamlit viewer** -- web UI with Document Explorer, record navigator, and search
- **Export inventory** -- single-command completeness check across all categories (``sf inventory``)
- **Idempotent & resumable** -- all operations support resume; re-run to pick up where you left off
- **Verification & retry** -- SHA-256 integrity checks with automatic retry of failed downloads

Two CLIs
========

===============  ============================================
``sf``           Simple commands for daily use
``sfdump``       Full CLI with all advanced options
===============  ============================================

::

    # Simple workflow
    sf dump                   # Export everything from Salesforce
    sf view                   # Browse exported data in web viewer
    sf inventory              # Check export completeness
    sf sins                   # Download invoice PDFs
    sf status                 # List available exports
    sf usage                  # Check API usage / limits

    # Advanced
    sfdump files              # Export Attachments/ContentVersions
    sfdump csv                # Export specific objects to CSV
    sfdump verify-files       # Verify file integrity (SHA-256)
    sfdump retry-missing      # Retry failed downloads
    sfdump inventory -v       # Detailed completeness report
    sfdump build-db           # Build SQLite database
    sfdump db-viewer          # Launch Streamlit viewer
    sfdump docs-index         # Rebuild document indexes

Export Inventory
================

The ``inventory`` command provides a single authoritative answer to
"is my export complete?" by inspecting only local files (no API calls)::

    $ sf inventory

    Export Inventory
    ==================================================
    Location:  ./exports/export-2025-03-15

      Category             Status         Expected     Present
      CSV Objects          COMPLETE             44          44
      Attachments          COMPLETE         12,456      12,456
      ContentVersions      COMPLETE            285       1,194
      Invoice PDFs         INCOMPLETE        1,200           0  (1,200 missing)
      Indexes              COMPLETE             11          11
      Database             COMPLETE                  14 tables

      Overall: INCOMPLETE

The inventory checks six categories:

- **CSV Objects** -- all 44 essential Salesforce objects present
- **Attachments** -- legacy file downloads verified against metadata
- **ContentVersions** -- modern file downloads verified against metadata
- **Invoice PDFs** -- FinancialForce/Coda invoice PDFs (``c2g__codaInvoice__c``)
- **Indexes** -- per-object file indexes and master document index
- **Database** -- SQLite database tables and row counts

Use ``--json-only`` for machine-readable output. The manifest is also
auto-generated at ``meta/inventory.json`` after every ``sf dump`` run.

Installation
============

All Platforms (PyPI)
--------------------

If you have Python 3.12+ installed::

    pip install sfdump

To upgrade::

    pip install --upgrade sfdump

Windows (Starting from Nothing)
-------------------------------

**Option 1: One-Line Install (Recommended)**

Open PowerShell (press Win+R, type ``powershell``, press Enter) and paste::

    irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex

This downloads and installs everything automatically.

**Detailed Instructions**

See `INSTALL.md <INSTALL.md>`_ for step-by-step instructions with screenshots
and troubleshooting tips.

**Requirements**

- Windows 10 or 11
- 40 GB free disk space (for Salesforce exports)
- Internet connection
- No administrator rights required

macOS / Linux
-------------

::

    pip install sfdump

For development (contributors)::

    git clone https://github.com/ksteptoe/sfdump.git
    cd sfdump
    make bootstrap

Quick Start
===========

::

    # First time: configure credentials
    sf setup                  # Interactive .env creation
    sf test                   # Verify connection

    # Export
    sf dump                   # Full export (files + CSVs + database)
    sf dump --retry           # Export and retry failed downloads

    # Browse offline
    sf view                   # Launch Streamlit viewer

    # Completeness check
    sf inventory              # Are we done?

Configuration
=============

Create a ``.env`` file in your working directory (or use ``sf setup``)::

    SF_AUTH_FLOW=client_credentials
    SF_CLIENT_ID=<your_consumer_key>
    SF_CLIENT_SECRET=<your_consumer_secret>
    SF_LOGIN_URL=https://yourcompany.my.salesforce.com

For invoice PDF downloads, a Web Server OAuth flow is also needed::

    sfdump login-web          # Opens browser for SSO login

Invoice PDFs
============

Invoice PDFs are generated on-the-fly by a Visualforce page in Salesforce --
they are **not** stored as files. A deployed Apex REST class
(``SfdumpInvoicePdf``) renders each invoice to PDF server-side.

::

    sfdump login-web          # Authenticate via browser (SSO)
    sf sins                   # Download all Complete invoice PDFs
    sf sins --force           # Re-download everything

PDFs are saved to ``{export}/invoices/SIN001234.pdf`` and indexed for the
viewer's Document Explorer.

Work in Progress
================

Invoice PDF Pipeline
--------------------

**Status**: The Apex REST endpoint is deployed to production and the ``sf sins``
command works end-to-end. The remaining gap is that the Web Server OAuth token
(``sfdump login-web``) needs to be refreshed manually. The ``sf dump``
orchestrator will attempt invoice PDF downloads automatically if a valid web
token exists, but falls back gracefully if not.

**What's deployed in Salesforce**:

- Apex class ``SfdumpInvoicePdf`` -- REST endpoint at
  ``/services/apexrest/sfdump/invoice-pdf?id={invoiceId}``
- Test class ``SfdumpInvoicePdfTest`` -- 94% coverage
- These are read-only and harmless; recommend keeping them permanently

**Known limitation**: The org uses SSO (SAML), so the ``client_credentials``
OAuth flow cannot render Visualforce pages. Invoice PDF download requires the
Web Server (Authorization Code + PKCE) flow which produces a real user session.

Export Completeness Direction
-----------------------------

The ``sf inventory`` command is the foundation for a broader completeness
guarantee. The direction:

1. **Inventory system** (done) -- offline checks across all six categories,
   JSON manifest at ``meta/inventory.json``, auto-generated after each export
2. **CI integration** -- use ``sf inventory --json-only`` in pipelines to
   assert export completeness before archival
3. **Drift detection** -- compare inventory manifests over time to detect
   regressions (e.g. files deleted, database corruption)
4. **Archival sign-off** -- once all categories show COMPLETE, the export
   can be confidently archived as the authoritative copy of the org's data

Architecture
============

::

    Salesforce API --> api.py --> files.py --> CSV + binary exports
                                    |
                                verify.py (SHA-256 completeness)
                                    |
                                retry.py (failure recovery)
                                    |
                              inventory.py (completeness check)
                                    |
                               indexing/ (document indexes)
                                    |
                         viewer/ + viewer_app/ (SQLite + Streamlit)

Export directory structure::

    exports/export-2026-01-26/
        csv/                    # 44 Salesforce objects as CSV
        files/                  # ContentVersion binaries
        files_legacy/           # Attachment binaries
        invoices/               # Invoice PDFs (SIN*.pdf)
        links/                  # Metadata CSVs + file indexes
        meta/
            sfdata.db           # SQLite database
            inventory.json      # Completeness manifest
            master_documents_index.csv

.. _pyscaffold-notes:

Making Changes & Contributing
=============================

This project uses `pre-commit`_, please make sure to install it before making any
changes::

    pip install pre-commit
    cd sfdump
    pre-commit install

It is a good idea to update the hooks to the latest version::

    pre-commit autoupdate

Don't forget to tell your contributors to also install and use pre-commit.

.. _pre-commit: https://pre-commit.com/

Note
====

This project has been set up using PyScaffold 4.6. For details and usage
information on PyScaffold see https://pyscaffold.org/.
