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

Windows (Recommended for Non-Technical Users)
---------------------------------------------

**Option 1: One-Click Install**

1. Download or clone this repository
2. Double-click ``install.bat``
3. Follow the prompts (Python will be installed if needed)

**Option 2: PowerShell**

Right-click ``setup.ps1`` and select "Run with PowerShell", or run::

    powershell -ExecutionPolicy Bypass -File setup.ps1

**Troubleshooting: "Python was not found" Error**

If you see this error, the Microsoft Store Python alias is interfering:

1. Open Windows Settings (Win + I)
2. Go to: Apps > Advanced app settings > App execution aliases
3. Turn OFF both ``python.exe`` and ``python3.exe`` aliases
4. Install Python from https://www.python.org/downloads/
5. **Important**: Check "Add Python to PATH" during installation

macOS / Linux
-------------

::

    # Requires Python 3.12+
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
