# CLI Reference

This document lists all sfdump CLI commands.

## `sfdump verify-files`

Check for missing or zero-byte files.

## `sfdump retry-missing`

Retry files listed in missing CSVs.

## `sfdump analyze-missing`

Map missing files to parent records.

## `sfdump report-missing`

Generate Markdown/PDF reports (redacted or full).

## New Flags

### `--redact`
Hides sensitive IDs and filenames.

### Verbosity

```
-v   → INFO
-vv  → DEBUG
```

## Environment Flags

- `SFDUMP_FILES_ORDER`
- `SFDUMP_FILES_CHUNK_TOTAL`
- `SFDUMP_FILES_CHUNK_INDEX`
