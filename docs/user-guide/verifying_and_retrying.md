# Verifying and Retrying Missing Files

This page explains how sfdump detects missing files, how to retry downloads, and how the system guarantees completeness.

## 1. Verify Export Completeness

Run:

```bash
sfdump verify-files --export-dir exports/export-YYYY-MM-DD/files
```

This scans:

- `files/`
- `files_legacy/`
- metadata CSVs in `links/`

Outputs:

- `attachments_missing.csv`
- `content_versions_missing.csv`

You want both to be empty.

## 2. Retry Missing Files

```bash
sfdump retry-missing --export-dir exports/export-YYYY-MM-DD/files -v
```

This will:

- login to Salesforce
- re-download missing files
- record retry results in:
  - `attachments_missing_retry.csv`
  - `content_versions_missing_retry.csv`

Columns include:

- `retry_success`
- `retry_error`
- `retry_status`

## 3. Typical Causes of Missing Files

- Salesforce API limits causing partial zero-byte responses
- Attachments no longer stored in org (archived or purged)
- Restricted Parent object the API can see but cannot download from
- Network drop during a long export

## 4. How Retry Logic Works

It attempts each file again with:

- direct API call
- additional debug logging when `-v` or `-vv` is used
- local overwrite only when successful

## 5. After Retry

Run verify again:

```bash
sfdump verify-files --export-dir exports/export-YYYY-MM-DD/files
```

If everything is recovered, both CSVs should be empty.
