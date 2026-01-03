# Quickstart

The fastest way to perform a full export, verify completeness, and create a searchable archive.

## 1. Set Credentials

```bash
export SF_CLIENT_ID="xxx"
export SF_CLIENT_SECRET="yyy"
export SF_LOGIN_URL="https://login.salesforce.com"
```

## 2. Export

```bash
make -f Makefile.export export-files
```

This exports all Salesforce data and files to `exports/export-YYYY-MM-DD/`.

## 3. Verify

```bash
sfdump verify-files --export-dir exports/export-YYYY-MM-DD/files
```

Checks that all files downloaded successfully.

## 4. Retry

```bash
sfdump retry-missing --export-dir exports/export-YYYY-MM-DD/files -v
```

Re-downloads any files that failed.

## 5. Generate Report

```bash
sfdump report-missing --export-dir exports/export-YYYY-MM-DD --out docs/missing_report --redact
```

Creates a summary report of any missing files.

## 6. Build Searchable Database

```bash
sfdump build-db -d exports/export-YYYY-MM-DD --overwrite
```

**What this does:**
- Converts CSV exports into a SQLite database
- Creates indexes for fast searching
- Builds document index for file search
- Output: `exports/export-YYYY-MM-DD/meta/sfdata.db`

**Time:** 1-5 minutes depending on data size

## 7. Launch Viewer

```bash
sfdump db-viewer --db exports/export-YYYY-MM-DD/meta/sfdata.db
```

**What this does:**
- Starts a web-based viewer on http://localhost:8503
- Browse records, navigate relationships
- Search documents by Account/Opportunity
- Preview PDFs inline

**For detailed viewer usage, see:** [Database Viewer Guide](database_viewer.md)

## Complete Workflow Summary

| Step | Command | Time | Output |
|------|---------|------|--------|
| 1. Export | `make -f Makefile.export export-files` | 30-120 min | CSV files + documents |
| 2. Verify | `sfdump verify-files ...` | 1-5 min | Verification report |
| 3. Retry | `sfdump retry-missing ...` | 5-30 min | Missing files recovered |
| 4. Report | `sfdump report-missing ...` | 1 min | Missing file report |
| 5. **Build DB** | `sfdump build-db ...` | 1-5 min | **Searchable database** |
| 6. **View** | `sfdump db-viewer ...` | Instant | **Web interface** |

## Next Steps

**For end users finding documents:**
- See [Finding Documents Guide](finding_documents.md) - simplified for non-technical users

**For detailed viewer features:**
- See [Database Viewer Guide](database_viewer.md) - complete documentation

**For archiving before org shutdown:**
- See [FAQ](faq.md) - common questions about long-term archival
