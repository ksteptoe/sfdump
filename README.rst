.. These are examples of badges you might want to add to your README:
   please update the URLs accordingly

    .. only:: html

   .. image:: https://api.cirrus-ci.com/github/<USER>/sfdump.svg?branch=main
      :alt: Built Status
      :target: https://cirrus-ci.com/github/<USER>/sfdump

   .. image:: https://readthedocs.org/projects/sfdump/badge/?version=latest
      :alt: ReadTheDocs
      :target: https://sfdump.readthedocs.io/en/stable/

   .. image:: https://img.shields.io/coveralls/github/<USER>/sfdump/main.svg
      :alt: Coveralls
      :target: https://coveralls.io/r/<USER>/sfdump

   .. image:: https://img.shields.io/pypi/v/sfdump.svg
      :alt: PyPI-Server
      :target: https://pypi.org/project/sfdump/

   .. image:: https://img.shields.io/conda/vn/conda-forge/sfdump.svg
      :alt: Conda-Forge
      :target: https://anaconda.org/conda-forge/sfdump

   .. image:: https://pepy.tech/badge/sfdump/month
      :alt: Monthly Downloads
      :target: https://pepy.tech/project/sfdump

   .. image:: https://img.shields.io/twitter/url/http/shields.io.svg?style=social&label=Twitter
      :alt: Twitter
      :target: https://twitter.com/sfdump

   .. image:: https://img.shields.io/badge/-PyScaffold-005CA0?logo=pyscaffold
      :alt: Project generated with PyScaffold
      :target: https://pyscaffold.org/

|

======
sfdump
======

Salesforce data export and archival tool for bulk downloading Attachments and
ContentVersions, with verification, retry mechanisms, searchable SQLite database
creation, and a Streamlit web viewer.

Installation
============

Windows (Starting from Nothing)
-------------------------------

**Option 1: One-Line Install (Recommended)**

Open PowerShell (press Win+R, type ``powershell``, press Enter) and paste::

    irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex

This downloads and installs everything automatically.

**Option 2: Manual Download**

1. Go to https://github.com/ksteptoe/sfdump
2. Click the green "Code" button > "Download ZIP"
3. Extract the ZIP file
4. Double-click ``install.bat``

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

    git clone https://github.com/ksteptoe/sfdump.git
    cd sfdump
    pip install -e ".[dev]"

    # Or using make
    make bootstrap

Quick Start
===========

After installation::

    sfdump --help          # Show available commands
    sfdump login           # Authenticate with Salesforce
    sfdump files           # Export Attachments/ContentVersions
    sfdump build-db        # Build searchable SQLite database
    sfdump db-viewer       # Launch the web viewer

Configuration
=============

Create a ``.env`` file in your working directory::

    SF_CLIENT_ID=<your_consumer_key>
    SF_CLIENT_SECRET=<your_consumer_secret>
    SF_HOST=login.salesforce.com
    SF_USERNAME=user@example.com
    SF_PASSWORD=<password+security_token>

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
