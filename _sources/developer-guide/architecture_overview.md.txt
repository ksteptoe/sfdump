# Architecture Overview

`sfdump` is built around a modular architecture designed to safely export all Salesforce files, avoid API limits, and ensure completeness.

## Key Architectural Goals

- Reliable bulk export of Attachments and ContentVersions
- Automatic resume without re-downloading existing files
- Protection against Salesforce API limits
- Deep verification and retry mechanisms
- Automatic redacted/unredacted reporting
- Clean CLI and Makefile-driven interface

## High-Level Components

- **api.py** — Salesforce REST API wrapper
- **files.py** — File download logic (Attachments + ContentVersions)
- **dumper.py** — Export orchestration
- **verify.py** — Completeness checker
- **retry.py** — Retrying failed downloads
- **analyze.py** — Parent-object analysis
- **report.py** — Markdown/PDF report generator
- **cli.py** — User-facing command-line interface
- **Makefile.export** — Batch orchestration

## Export Lifecycle

1. Query metadata
2. Apply chunking/order
3. Download files
4. Build indexes
5. Verify completeness
6. Retry missing files
7. Produce audit-ready reports

`sfdump` ensures no step loses state, allowing users to safely re-run workflows.
