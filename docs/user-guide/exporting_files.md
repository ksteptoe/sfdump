# Exporting Files

This page documents all behaviours of the file export pipeline.

## Overview

`sfdump export-files` retrieves:
- All Salesforce **ContentVersions**
- All Salesforce **Attachments**
- Builds index files linking files to parent objects

## Resume Behaviour

Existing files are skipped automatically.
This reduces API usage and avoids re-downloading tens of thousands of files.

## Ordering

```bash
export SFDUMP_FILES_ORDER=desc
```

Descending ordering is useful when resuming interrupted exports.

## Chunking

Split work:

```bash
export SFDUMP_FILES_CHUNK_TOTAL=4
export SFDUMP_FILES_CHUNK_INDEX=1
```

## Output Structure

```
files/
files_legacy/
links/
```

Metadata CSVs include parent links, file metadata, and index maps.
