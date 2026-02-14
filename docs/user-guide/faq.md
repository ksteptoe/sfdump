# FAQ

Frequently asked questions about sfdump.

## General

### What does sfdump do?

sfdump exports all your Salesforce data (files, accounts, opportunities, invoices, etc.) to your local computer so you can access it offline. It's designed for organizations archiving data before shutting down their Salesforce instance.

### What gets exported?

- **Files** — All Attachments and Documents (ContentVersion)
- **Data** — Accounts, Contacts, Opportunities, Invoices, and other business records
- **Relationships** — Links between records are preserved

### How long does an export take?

Depends on your data size:
- Small org (< 10,000 files): Under an hour
- Medium org (10,000 - 100,000 files): Several hours
- Large org (100,000+ files): May take a day or more

You can interrupt and resume at any time.

## Running Exports

### What if the export is interrupted?

Just run `sf dump` again. Files already downloaded are skipped automatically. The export continues from where it stopped.

### Can I run the export multiple times?

Yes. It's safe to run `sf dump` as many times as needed:
- Already-downloaded files are skipped
- Only missing files are attempted
- No duplicates are created

### How do I export a specific date range?

sfdump exports all data by default. For filtered exports, use the advanced `sfdump` command with custom SOQL queries.

### Can I export to a network drive?

Yes. Specify the path when running the export:
```
sf dump --export-dir /path/to/network/drive/export
```

## Missing Files

### Why are some files missing?

Common reasons:
- **Deleted from Salesforce** — File was removed after metadata was queried
- **No permission** — Your user doesn't have access to the parent record
- **Archived externally** — File was moved to external storage
- **Network issues** — Connection dropped during download

### Can I recover deleted files?

No. If a file was deleted from Salesforce, it no longer exists and cannot be recovered. The export will note these as "404 Not Found".

### What does "zero-byte file" mean?

Sometimes Salesforce returns an empty response due to API limits. Run `sf dump` again — the retry logic will re-attempt these downloads.

### Should I worry about a few missing files?

Usually not. A 99%+ complete export is normal. Files get deleted over time as part of normal business operations. Review the missing files list to confirm they're not critical.

## Viewing Data

### How do I browse my exported data?

Run:
```
sf view
```

This opens a web browser with an interactive viewer where you can search and navigate your data.

### Can multiple people use the viewer?

Yes. Share the Network URL shown when you start the viewer:
```
Network URL: http://192.168.1.100:8503
```

Anyone on your local network can access it.

### Can I search across all documents?

Yes. The viewer opens in Explorer mode where you can search by Account name, Opportunity name, invoice number, or any keyword to find all related documents.

### How do I find a specific invoice?

1. Type the invoice number in the search box (e.g., "SIN002795")
2. Click the matching result to preview the document
3. Click **Open parent record** to see the full invoice details in DB Viewer

## Reports

### Do I need Pandoc for PDF reports?

Only if you want PDF output. Markdown reports (`.md`) always work without additional software.

### Where should I store full (unredacted) reports?

Never commit them to Git or share externally. Store them in a private folder:
- Local encrypted drive
- Private network share
- Secure document management system

### What's the difference between redacted and full reports?

| Report Type | Contains | Use For |
|-------------|----------|---------|
| Redacted | `[REDACTED]` placeholders | External sharing, auditors, documentation |
| Full | Actual IDs and filenames | Internal IT review, troubleshooting |

## Technical

### What credentials do I need?

You need a Salesforce Connected App with:
- Consumer Key (Client ID)
- Consumer Secret
- Your Salesforce username and password

Contact your Salesforce administrator or IT department.

### Where are credentials stored?

In a `.env` file in your sfdump directory. This file contains sensitive information — don't share it or commit it to Git.

### How much disk space do I need?

Depends on your Salesforce data:
- Check your Salesforce file storage usage for an estimate
- Plan for at least 40GB free space for medium-sized orgs
- Large orgs may need 100GB+

### Can I run exports on a schedule?

Yes. Run `sf dump` from a scheduled task (Windows) or cron job (Mac/Linux). The resume feature ensures interrupted exports continue automatically.

### What if I have a very large org?

Use chunking to split the export:
```bash
export SFDUMP_FILES_CHUNK_TOTAL=4
export SFDUMP_FILES_CHUNK_INDEX=1
sf dump
```

Run with INDEX=1, 2, 3, 4 to process in parallel or across multiple days.

## After Export

### How do I archive the export?

The export directory contains everything:
```
exports/export-2026-01-25/
├── files/          # Documents
├── files_legacy/   # Attachments
├── csv/            # Data files
├── links/          # Metadata
└── meta/           # Database
```

Copy this entire folder to your archive location.

### Can I access the data without the viewer?

Yes:
- **CSV files** — Open in Excel or any spreadsheet
- **SQLite database** — Query with any SQLite tool
- **Files** — Access directly in the `files/` folder

### How long should I keep the export?

Follow your organization's data retention policy. Exports are self-contained and don't depend on Salesforce, so they can be kept indefinitely.

### Can I import the data back into Salesforce?

sfdump is designed for archival, not migration. For re-importing data, you'd need Salesforce Data Loader or similar tools, plus the CSV files from your export.

## Getting Help

### Where do I report issues?

Open an issue at: https://github.com/ksteptoe/sfdump/issues

### Is there a support email?

Contact your IT administrator first. For technical issues, use the GitHub issues page.
