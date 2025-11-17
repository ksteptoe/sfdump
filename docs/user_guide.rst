User Guide
==========

.. contents::
   :local:
   :depth: 2

Overview
--------

``sfdump`` is a command-line tool for exporting data from Salesforce into
structured, offline archives. It retrieves Salesforce objects, files, and
metadata and consolidates them into a complete export package containing:

* CSV data extracts
* File attachments and content versions
* A manifest (``manifest.json`` and ``manifest.db``)
* A ZIP archive for long-term storage or transfer

It is designed for system administrators, compliance officers, and engineers
who need reliable, scriptable Salesforce data exports.

Features
--------

* OAuth2 authentication
* Graceful handling of missing credentials
* Modular CLI subcommands (``login``, ``objects``, ``csv``, ``files``, ``manifest``)
* Automatic ``.env`` loading for credentials
* Robust error and retry handling
* SHA-256 checksums for all downloaded files
* Manifest + SQLite database creation
* ZIP packaging of all exports
* Fully scriptable and version-controlled via Git + Makefile

Installation
------------

1. Clone the repository::

      git clone https://github.com/ksteptoe/sfdump.git
      cd sfdump

2. Create and activate a virtual environment::

      python -m venv .venv
      source .venv/Scripts/activate   # (Git Bash / Windows)

3. Install all dependencies::

      make bootstrap

4. Optionally install development tools::

      pip install -e .[dev]

Configuration
-------------

All Salesforce credentials are read from environment variables or a ``.env`` file.

Example ``.env`` file::

   SF_HOST=login.salesforce.com
   SF_CLIENT_ID=YOUR_CLIENT_ID
   SF_CLIENT_SECRET=YOUR_CLIENT_SECRET
   SF_USERNAME=YOUR_SF_USERNAME
   SF_PASSWORD=YOUR_SF_PASSWORD_AND_TOKEN

``sfdump`` automatically loads ``.env`` from the project root.

CLI Reference
-------------

General syntax::

   sfdump [OPTIONS] COMMAND [ARGS]...

Global options
~~~~~~~~~~~~~~

+----------------------+-----------------------------------------+
| Option               | Description                             |
+======================+=========================================+
| ``-v``               | Enable INFO-level logging               |
+----------------------+-----------------------------------------+
| ``-vv``              | Enable DEBUG-level logging              |
+----------------------+-----------------------------------------+
| ``--version``        | Show CLI version                        |
+----------------------+-----------------------------------------+
| ``-h``, ``--help``   | Show help message                       |
+----------------------+-----------------------------------------+

Subcommands
~~~~~~~~~~~

**login**

Authenticate with Salesforce and print identity + API info::

   sfdump login [--show-json]

* ``--show-json`` – prints raw JSON for both user info and API limits.

Example::

   sfdump login --show-json

**objects**

List all Salesforce objects available in your org::

   sfdump objects [--all]

If credentials are missing, ``sfdump`` displays a friendly message::

   Error: Missing Salesforce credentials.
   Please ensure SF_CLIENT_ID, SF_CLIENT_SECRET, SF_USERNAME, SF_PASSWORD are set.

**csv**

Export a Salesforce object as CSV::

   sfdump csv OBJECTNAME [--out DIR] [--fields FIELDLIST]

Examples::

   # Export all Account records to CSV
   sfdump csv Account --out ./exports

   # Export selected fields only
   sfdump csv Contact --fields "Id,Name,Email" --out ./exports

Creates ``exports/Account.csv`` (or similar).

**files**

Export Salesforce attachments and content files::

   sfdump files --out ./exports/files

Each file is stored with a sanitized filename and SHA-256 checksum.
Two metadata CSVs are created: ``attachments.csv`` and ``content_versions.csv``.

.. include:: sfdump_files_cli_section.rst

**manifest**

Generate a manifest and bundle all exports into an archive::

   sfdump manifest [--root DIR]

Example::

   sfdump manifest --root ./exports

Creates::

   exports/
   ├── manifest.json
   ├── manifest.db
   └── sfdump-export-YYYYMMDD.zip

Error Handling
--------------

``sfdump`` handles errors gracefully.

+--------------------------------+----------------------------------------+-------------------------------------------+
| Error                          | Cause                                  | Resolution                                |
+================================+========================================+===========================================+
| Missing Salesforce credentials | ``.env`` missing or incomplete         | Create ``.env`` with required values      |
+--------------------------------+----------------------------------------+-------------------------------------------+
| Authentication failure         | Wrong password or token                | Verify ``SF_PASSWORD`` includes token     |
+--------------------------------+----------------------------------------+-------------------------------------------+
| HTTP 429                       | API rate limit exceeded                | Wait and retry                            |
+--------------------------------+----------------------------------------+-------------------------------------------+
| No such object                 | Invalid Salesforce object name         | Use ``sfdump objects --all`` to confirm   |
+--------------------------------+----------------------------------------+-------------------------------------------+

Example Workflow
----------------

::

   # 1. Check login
   sfdump login

   # 2. See available objects
   sfdump objects --all

   # 3. Export selected data
   sfdump csv Account --out ./exports
   sfdump files --out ./exports

   # 4. Generate manifest + ZIP
   sfdump manifest --root ./exports

Result::

   exports/
   ├── Account.csv
   ├── attachments/
   ├── content_versions/
   ├── manifest.json
   ├── manifest.db
   └── sfdump-export-2025-11-09.zip

Testing
-------

Run unit tests::

   make test

Run all tests with coverage::

   make test-all

Versioning and Releases
-----------------------

``sfdump`` follows `Semantic Versioning <https://semver.org>`_.

Common release Makefile targets:

- ``make release-show``
  Show current tag and inferred version.

- ``make release-patch``
  Bump patch version (``vX.Y.Z → vX.Y.Z+1``).

- ``make release-minor``
  Bump minor version (``vX.Y.Z → vX.Y+1.0``).

- ``make release-major``
  Bump major version (``vX.Y.Z → vX+1.0.0``).

Each release ensures:

* Working directory is clean
* Branch is up-to-date with ``origin``
* Tag is created and pushed automatically

Logging
-------

Logs are printed to stdout. Use verbosity flags for detail:

* ``-v``  – INFO messages
* ``-vv`` – DEBUG messages (includes API requests and responses)

Example::

   sfdump -vv csv Contact --out ./exports

File Structure
--------------

.. code-block:: text

   src/sfdump/
   ├── api.py              # Salesforce REST client
   ├── cli.py              # CLI entrypoint
   ├── command_objects.py  # Objects subcommand
   ├── command_csv.py      # CSV export subcommand
   ├── command_files.py    # File export subcommand
   ├── command_manifest.py # Manifest + ZIP packaging
   ├── dumper.py           # CSV and file helpers
   ├── utils.py            # Directory, checksum, and file utilities
   ├── exceptions.py       # Custom exception types
   └── logging_config.py   # Centralized logging setup

Offline document search after Salesforce shutdown
-------------------------------------------------

If you are planning to switch off your Salesforce instance, you can
still give legal and finance a searchable archive of all documents.

After running a full export (see :doc:`export_guide`), SFdump can build
a *master documents index* for each export run:

- Run the files export with ``--index-by`` for the key sObjects
  (Opportunity, Account, billing/ERP objects, etc.).
- Run ``sfdump docs-index --export-root /path/to/export-YYYY-MM-DD`` to
  create ``meta/master_documents_index.csv``.

This single CSV can then be used by a separate document browser (for
example a small Streamlit app or an Excel / Power BI report) to search
for documents by name, parent record, Account or Opportunity, and open
them directly from the exported file system.

Summary
-------

``sfdump`` provides a complete, auditable data-export pipeline for Salesforce:

1. Connect securely
2. Extract structured data and files
3. Build manifest and archive
4. Verify integrity

Built for transparency, reliability, and repeatability.
