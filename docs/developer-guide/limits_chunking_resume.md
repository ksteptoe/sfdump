# Limits, Chunking and Resume Strategy

Salesforce imposes strict API limits. sfdump includes a robust system to avoid hitting them.

## Resume Logic

If a file exists locally:
- It is skipped
- Saves API calls
- Enables safe reruns

## Ordering

Use descending order to recover from interrupted runs:

```bash
export SFDUMP_FILES_ORDER=desc
```

## Chunking

Divide work into slices to avoid API throttling:

```bash
export SFDUMP_FILES_CHUNK_TOTAL=4
export SFDUMP_FILES_CHUNK_INDEX=2
```

Each chunk receives:

- subset of ContentVersions
- subset of Attachments

Chunk flow:

1. Query all metadata
2. Slice locally
3. Download only that slice

## Limit Failure Behaviour

If Salesforce returns:
- `REQUEST_LIMIT_EXCEEDED`
- 0‑byte response bodies
- Connection abort during bulk download

You can always rerun safely.

## Recommended Pattern

1. Run chunked export
2. Verify
3. Retry
4. Generate report

This ensures completeness.
