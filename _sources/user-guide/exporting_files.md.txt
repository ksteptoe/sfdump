# Exporting Files

How to export files from Salesforce and what to expect.

## Basic Export

To export all files from Salesforce:

```
sf dump
```

This downloads:

- **Documents** (ContentVersion) — Files uploaded to Salesforce Files, Notes, and Libraries
- **Attachments** — Legacy files attached directly to records

No additional commands needed. The export handles everything automatically.

## What Gets Downloaded

| Type | Description | Location |
|------|-------------|----------|
| Documents | Modern Salesforce Files (PDFs, images, etc.) | `files/` |
| Attachments | Legacy attachments on records | `files_legacy/` |
| Metadata | File details and parent record links | `links/` |

## Resume and Retry

**Interrupted export?** Just run `sf dump` again.

- Files already downloaded are skipped automatically
- Failed downloads are retried
- Progress continues from where it stopped

This is safe to run multiple times — it won't duplicate files or waste API calls.

## Checking Export Status

To see what's been exported:

```
sf status
```

This shows:

- Available exports and their dates
- Number of files downloaded
- Number of objects exported
- Whether the database is ready

## Output Structure

After export, your folder looks like this:

```
exports/export-2026-01-25/
├── files/              # Documents (ContentVersion)
├── files_legacy/       # Attachments
├── csv/                # Object data (Account.csv, etc.)
├── links/              # Metadata and indexes
│   ├── content_versions.csv
│   ├── attachments.csv
│   └── ...
└── meta/
    ├── sfdata.db       # SQLite database for viewer
    └── master_documents_index.csv
```

## Viewing Exported Files

To browse your exported files:

```
sf view
```

This opens a web interface where you can search by Account or Opportunity and see all related documents.

## Advanced Options

These options are for power users with large Salesforce orgs.

### Download Order

To download newest files first (useful for large exports):

```bash
export SFDUMP_FILES_ORDER=desc
sf dump
```

### Chunking for Large Orgs

For very large Salesforce orgs, split the export across multiple runs:

```bash
# Run 1 of 4
export SFDUMP_FILES_CHUNK_TOTAL=4
export SFDUMP_FILES_CHUNK_INDEX=1
sf dump

# Run 2 of 4
export SFDUMP_FILES_CHUNK_INDEX=2
sf dump
```

This divides files into chunks so you can run exports in parallel or spread them over multiple days.

### Verbose Output

To see detailed progress for each file:

```
sf dump -v
```

## Next Steps

- [Verifying and Retrying](verifying_and_retrying.md) — Manual verification options
- [Generating Reports](generating_reports.md) — Create reports of missing files
