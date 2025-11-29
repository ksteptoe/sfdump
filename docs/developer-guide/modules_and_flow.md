# Modules and Data Flow

This page documents how each module interacts.

## Module Breakdown

### api.py
- Authenticates with Salesforce
- Wraps REST calls with retries
- Logs all HTTP interactions

### files.py
- Queries Attachments and ContentVersions
- Applies chunking
- Downloads binaries
- Writes metadata CSVs

### dumper.py
Central orchestrator for the full export.

### verify.py
- Scans filesystem
- Compares against metadata CSVs
- Produces missing-file CSVs

### retry.py
- Attempts to re-download missing files
- Writes retry CSVs

### analyze.py
- Maps failed files to parent records
- Identifies impacted business objects

### report.py
- Assembles all diagnostics into Markdown/PDF
- Handles redaction
- Injects logos

### cli.py
- Ties everything together
- Provides user-friendly commands

## Data Flow Diagram (Text)

```
Salesforce → api.py → files.py → dumps
                          ↓
                     verify.py
                          ↓
                     retry.py
                          ↓
                    analyze.py
                          ↓
                     report.py
```
