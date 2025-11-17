.. _finance-user-guide:

Finance User Guide: Salesforce Document Archive
===============================================

.. note::

   **Internal – Finance users only.** This document describes how to run
   exports and use the offline Salesforce document archive. It assumes the
   SFdump tooling has already been installed and configured by IT.


Overview
--------

This guide explains how Finance can use the Salesforce document archive:

- A secure folder in OneDrive where regular exports are stored.
- A simple browser-based viewer for searching and opening documents.
- No Salesforce login required for day-to-day use.

The setup is designed so that:

- IT or a technical owner configures the tool once.
- Finance can then run one command to **update the export** and one command to
  **view and open documents**.


1. Technical Setup (Performed Once by IT)
-----------------------------------------

The steps in this section are typically done by IT / Sales Ops / a technical
user. Finance users only need the later sections on running exports and using
the viewer.

1.1. Install SFdump and Create the Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Create a folder for the SFdump code, for example::

      C:\Users\<you>\OneDrive\py\sfdump

2. Place the SFdump project in this folder (for example, by cloning it from
   Git or copying from an internal source).

3. Open a terminal (e.g. Git Bash) and create a virtual environment::

      cd ~/OneDrive/py/sfdump
      python -m venv .venv

4. Activate the virtual environment::

      source .venv/Scripts/activate

5. Install dependencies and initialise the project. The exact command may vary
   by repository; a common pattern is::

      make bootstrap

   This typically installs all required Python packages and ensures that the
   ``sfdump`` command is available inside the virtual environment.


1.2. Connect SFdump to Salesforce
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure Salesforce API access using the chosen method (for example JWT-based
OAuth). This is environment-specific and usually handled by IT.

Once configured, verify that SFdump can communicate with Salesforce. For
example, run::

    sfdump objects --all

If this returns a list of objects, the connection is working and the backend
is ready. Finance users do **not** need to know how this works; they only use
the export and viewer commands.


2. Create a Secure OneDrive Area for Finance
--------------------------------------------

All exported data should live in a **Finance-owned**, access-controlled
OneDrive folder, separate from the source code.

A typical structure is::

    C:\Users\<you>\OneDrive - <Company>\SF\

Within this folder, the system will later create::

    SF/
      ├─ Makefile.export
      └─ exports/
          ├─ export-YYYY-MM-DD/
          ├─ export-YYYY-MM-DD/
          └─ ...

Recommendations:

- Choose an internal OneDrive location that is appropriately secure for
  commercial and financial documents.
- Ensure Finance and any relevant stakeholders have read/write access.
- Treat this folder as sensitive (contracts, invoices, HR-related files, etc.).

Finance users will only work in this **SF** folder; they do not need access
to the SFdump source code folder.


3. Copy the Export Makefile into the Finance Folder
---------------------------------------------------

To make exports easy to run, we use a dedicated Makefile.

From the SFdump source directory, copy the export Makefile into the Finance
OneDrive folder. For example::

    cd ~/OneDrive/py/sfdump
    cp Makefile.export "C:/Users/<you>/OneDrive - <Company>/SF/Makefile.export"

After this, the Finance working area looks like::

    C:\Users\<you>\OneDrive - <Company>\SF\
      ├─ Makefile.export
      └─ exports\   (will be created automatically on first export)


4. Running the Export (Finance Routine)
---------------------------------------

This is the typical **Finance workflow** for updating the archive with a new
snapshot from Salesforce.

4.1. Open a Terminal and Activate the Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Open Git Bash (or another terminal).
2. Change directory to the Finance SF folder, e.g.::

      cd "C:/Users/<you>/OneDrive - <Company>/SF"

3. Activate the SFdump virtual environment from the code folder::

      source ~/OneDrive/py/sfdump/.venv/Scripts/activate

   (IT can optionally provide a shortcut or script to automate steps 1–3.)


4.2. Run the Full Export
~~~~~~~~~~~~~~~~~~~~~~~~

To run a full export into a date-stamped folder, use::

    make -f Makefile.export export-all BASE_EXPORT_ROOT="C:/Users/<you>/OneDrive - <Company>/SF"

What this does:

- Creates (if not already present) an ``exports`` directory under the SF folder.
- Creates a subdirectory for the run, named like::

      exports/export-YYYY-MM-DD/

- Downloads Salesforce data and files, including:

  - Files and attachments.
  - Core CRM objects (e.g. Account, Contact, Opportunity, etc.).
  - FinancialForce / ERP objects (if configured).
  - HR / Employment objects (if configured).

- Builds:

  - Per-object file index CSVs under::

        exports/export-YYYY-MM-DD/files/links/

  - A master document index under::

        exports/export-YYYY-MM-DD/meta/master_documents_index.csv


5. Viewing and Opening Documents
--------------------------------

Once an export is available, Finance can use the **browser-based viewer** to
search, filter and open documents without logging into Salesforce.

5.1. Launch the Viewer
~~~~~~~~~~~~~~~~~~~~~~

With the virtual environment active and the current directory set to the SF
folder, run::

    sfdump viewer

The viewer will:

- Start a local web server.
- Open a browser window (typically at ``http://localhost:8501``).
- Detect the ``exports`` directory.
- Identify all ``export-YYYY-MM-DD`` folders.
- Automatically select the **latest** export by default.

No Salesforce login is required for this step.

If needed, the base exports directory can be specified explicitly::

    sfdump viewer --exports-base "C:/Users/<you>/OneDrive - <Company>/SF/exports"


5.2. Using the Viewer
~~~~~~~~~~~~~~~~~~~~~

The viewer interface has two main areas:

**1. Left sidebar (configuration and filters)**

- **Exports base folder** – points to the shared OneDrive SF/exports area.
- **Export run** – defaults to the latest ``export-YYYY-MM-DD`` folder, but
  allows switching to earlier runs if needed.
- **Filters**:
  - Object types (e.g. Opportunity, Account, Invoice, Engineer__c).
  - File extensions (e.g. PDF, DOCX, XLSX).
- **Search box**:
  - Searches across file names, record names, object types, account names and
    opportunity fields.
  - Simple ``*`` wildcard is supported (e.g. ``*contract*``).

**2. Main panel (list of documents)**

- Displays up to **500 matching documents** from the current export.
- Typical columns include:
  - File source (Attachment vs File).
  - File name and extension.
  - Salesforce object type (e.g. Opportunity, Account).
  - Record name (e.g. opportunity or account name).
  - Account and opportunity details (stage, amount, close date).
- Shows a summary message such as::

    Viewer loaded successfully — 3,842 total documents indexed.


5.3. Opening a Document
~~~~~~~~~~~~~~~~~~~~~~~

At the bottom of the viewer page there is an **Open a document** section:

1. Use the filters and search to narrow down to the relevant document(s).
2. In the selection box, choose the desired document (by file name and
   related record).
3. Click the **Open** button.

The viewer will:

- Resolve the file’s path within the export folder.
- Open the document in its default application on your system (e.g. PDF
  reader, Word, Excel).

If a file cannot be opened (for example, if it was moved or not downloaded),
the viewer will show a clear message including the path it attempted to use.


6. Typical Day-to-Day Workflow (Finance)
----------------------------------------

In practice, a typical cycle for Finance looks like this:

1. **Update the archive** (e.g. daily, weekly or monthly)::

      cd "C:/Users/<you>/OneDrive - <Company>/SF"
      source ~/OneDrive/py/sfdump/.venv/Scripts/activate
      make -f Makefile.export export-all BASE_EXPORT_ROOT="C:/Users/<you>/OneDrive - <Company>/SF"

2. **Browse and open documents**::

      sfdump viewer

3. Use the viewer’s filters and search to find the relevant documents and
   open them as needed.


7. Support and Maintenance
--------------------------

- IT / the technical owner is responsible for:
  - Maintaining the SFdump code and virtual environment.
  - Keeping the Salesforce API credentials up to date.
  - Updating the Makefile or viewer behaviour if the data model changes.

- Finance users are responsible for:
  - Running the export at the agreed cadence.
  - Using the viewer for read-only access to the exported documents.
  - Escalating to IT if:
    - The export fails.
    - The viewer shows errors about missing or unreadable indexes.
    - Files cannot be opened despite recent exports.
