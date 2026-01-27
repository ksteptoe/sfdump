# Verifying and Retrying

How sfdump ensures all your files are downloaded completely.

## Automatic Verification

When you run `sf dump`, verification happens automatically:

1. Downloads all files from Salesforce
2. Checks that each file was saved correctly
3. Retries any failed downloads
4. Reports final status

You don't need to run separate verify or retry commands.

## Checking Results

At the end of an export, you'll see a summary:

```
==================================================
Export Summary
==================================================

  Location:   /home/user/sfdump/exports/export-2026-01-25

  Files:
    Expected:   12,847
    Downloaded: 12,845
    Missing:    2
    Complete:   99.98%

  Status: NEARLY COMPLETE - 2 files could not be retrieved
          (These may have been deleted from Salesforce)
```

### What the Status Means

| Status | Meaning |
|--------|---------|
| **COMPLETE** | All files downloaded successfully |
| **NEARLY COMPLETE** | 99%+ downloaded, missing files may be deleted from Salesforce |
| **INCOMPLETE** | Run `sf dump` again to continue downloading |

## Re-running the Export

If files are missing, simply run:

```
sf dump
```

This is safe to run multiple times:

- Already-downloaded files are skipped
- Only missing files are attempted
- Progress is preserved between runs

## Why Files Might Be Missing

Some files cannot be downloaded. Common reasons:

| Reason | Explanation |
|--------|-------------|
| **Deleted in Salesforce** | File was removed after metadata was queried |
| **Permission restricted** | Your user doesn't have access to the parent record |
| **Archived content** | File was moved to external storage |
| **Network interruption** | Connection dropped during download |

Files deleted from Salesforce cannot be recovered — they no longer exist.

## Viewing Missing Files

To see which files are missing, check the master index:

```
exports/export-2026-01-25/meta/master_documents_index.csv
```

Files with an empty `local_path` column were not downloaded.

## Advanced: Manual Verification

For detailed control, use the full `sfdump` commands:

### Verify Only

```bash
sfdump verify-files --export-dir exports/export-2026-01-25/files
```

Creates:
- `links/attachments_missing.csv`
- `links/content_versions_missing.csv`

### Retry Only

```bash
sfdump retry-missing --export-dir exports/export-2026-01-25/files -v
```

Attempts to re-download files listed in the missing CSVs.

### Analyze Missing Files

```bash
sfdump analyze-missing --export-dir exports/export-2026-01-25
```

Shows breakdown of why files are missing (permissions, deleted, etc.).

## Next Steps

- [Generating Reports](generating_reports.md) — Create reports for audit or compliance
- [FAQ](faq.md) — Common questions about missing files
