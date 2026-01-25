# Quickstart

Get up and running with sfdump in 3 simple commands.

## Prerequisites

- sfdump installed (see [Installation](installation.md))
- Salesforce Connected App credentials from your IT department

## Step 1: Configure Credentials

Run the setup wizard:

```
sf setup
```

You'll be prompted for:

- **Consumer Key** — from your Salesforce Connected App
- **Consumer Secret** — from your Salesforce Connected App
- **Username** — your Salesforce login email
- **Password + Security Token** — your password with security token appended

This creates a `.env` file with your credentials.

## Step 2: Test Connection

Verify your credentials work:

```
sf test
```

You should see:

```
Testing Salesforce Connection
==================================================
Config: C:\Users\YourName\sfdump\.env

Connecting... OK
Instance: https://yourcompany.my.salesforce.com
Testing query... OK

Connection successful! Ready to export.
```

## Step 3: Export Your Data

Run the export:

```
sf dump
```

This automatically:

1. Authenticates to Salesforce
2. Downloads all Attachments and Documents
3. Exports Account, Contact, Opportunity, Invoice, and other business data
4. Builds searchable indexes
5. Creates a SQLite database for offline browsing
6. Verifies downloads and retries any failures

Output is saved to `./exports/export-YYYY-MM-DD/`.

### What Success Looks Like

After `sf dump` completes, you'll see a summary like this:

```
==================================================
Export Summary
==================================================

  Location:    ./exports/export-2026-01-25

  Files
    Expected:    12,479
    Downloaded:  12,456
    Missing:     23
    Complete:    99.8%

  NEARLY COMPLETE - 23 files could not be retrieved
  (These may have been deleted from Salesforce)

  Objects:  38
  Database: ./exports/export-2026-01-25/meta/sfdata.db

  To browse your data:
    sf view
```

**Understanding the summary:**

- **Downloaded** — Files successfully saved to your computer
- **Missing** — Files that no longer exist in Salesforce (this is normal)
- **Complete %** — 99%+ is excellent; 100% is rare due to normal deletions

## Step 4: Browse Your Data

Launch the viewer:

```
sf view
```

This opens a web browser where you can:

- Search by Account or Opportunity name
- Browse related documents
- Preview PDFs and images inline
- Navigate between linked records

## Command Summary

| Command | Description |
|---------|-------------|
| `sf setup` | Configure Salesforce credentials |
| `sf test` | Verify connection works |
| `sf dump` | Export everything from Salesforce |
| `sf view` | Browse exported data in web viewer |
| `sf status` | List available exports |

## Troubleshooting

**"SF_CLIENT_ID not set"** — Run `sf setup` to configure credentials.

**"Connection failed"** — Check your credentials with `sf test`. Verify your password includes the security token.

**Export incomplete** — Run `sf dump` again. It automatically retries failed downloads.

### Quick Troubleshooting Guide

```
Problem?
   │
   ├─ "SF_CLIENT_ID not set"
   │     └─ Run: sf setup
   │
   ├─ "Connection failed"
   │     ├─ Check password includes security token
   │     └─ Run: sf test
   │
   ├─ Export incomplete (< 95%)
   │     └─ Run: sf dump (again - it retries automatically)
   │
   └─ Viewer not loading
         └─ Keep terminal open, run: sf view
```

## Next Steps

- [Exporting Files](exporting_files.md) — Detailed export options
- [FAQ](faq.md) — Common questions about long-term archival

## Advanced Usage

For advanced options (custom objects, chunking, redaction), use the full `sfdump` command:

```
sfdump --help
```
