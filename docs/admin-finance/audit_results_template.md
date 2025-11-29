# Audit Results & Data Completeness (Template)

> ⚠️ **This template contains no proprietary data.**
> Actual results will be included at build time from `_generated/`.

## Overview

The export verification pipeline produces three primary artefacts:

1. `attachments_missing.csv`
2. `attachments_missing_retry.csv`
3. `missing_file_analysis.md`

These allow Finance and Audit teams to evaluate completeness.

## Runtime Inclusion

If real outputs exist under:

```
docs/_generated/audit/
```

they will be included automatically:

```md
:::{include} ../../_generated/audit/missing_file_analysis.md
:::
```
