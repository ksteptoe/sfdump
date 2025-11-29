# Redaction System

`sfdump` includes a deterministic redaction engine for safe sharing.

## What Is Redacted?

- Attachment IDs
- Parent IDs
- Filenames
- URLs

## Deterministic Mapping

Anonymised IDs are stable within a run:

```
ATTACHMENT_1 → maps to real attachment X
PARENT_1     → maps to real parent Y
```

## Where Redaction Applies

- Reports
- Diagnostic tables
- Parent impact summary

## Where It Does NOT Apply

- Local filesystem
- Internal reports
- Retry/verify CSVs

## How to Enable

```bash
sfdump report-missing --redact
```
