sfdump — Salesforce Data Export CLI
===================================

Welcome to the documentation for **sfdump**, a command-line tool that connects to Salesforce,
extracts your data and attachments, and packages everything into a manifest and ZIP archive
for long-term storage or analysis.

.. note::

   This documentation is generated using `Sphinx`_.
   You can rebuild it locally with::

       make -C docs html

   The table of contents below lists all available sections. Each corresponds
   to an ``.rst`` file under ``docs/``.


Contents
========

.. toctree::
   :maxdepth: 2
   :caption: User Documentation

   Overview <readme>
   User Guide <user_guide>
   Salesforce Export Guide <export_guide>
   Developer Guide <developer_guide>
   Contributions & Help <contributing>
   License <license>
   Authors <authors>
   Changelog <changelog>
   Module Reference <api/modules>


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


About this documentation
========================

This site is divided into two main parts:

1. **User Documentation** — everything you need to *use* the CLI:
   installation, authentication, and running commands like ``sfdump csv`` or ``sfdump manifest``.

2. **Developer Documentation** — information for contributors:
   internal module reference, development setup, and contribution guidelines.

Both are linked in the **Contents** tree above.

.. _Sphinx: https://www.sphinx-doc.org/en/master/

.. toctree::
   :maxdepth: 1
   :caption: Internal – Finance Only

   Finance User Guide <finance_user_guide>
