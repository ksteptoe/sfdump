# Generating Reports

Create reports for audits, compliance, or IT review.

## When to Generate Reports

Reports are useful for:

- **Audit trails** — Document what was exported and what's missing
- **Compliance** — Prove data retention requirements are met
- **IT/CFO review** — Share export status with stakeholders
- **Handover** — Document the export for future reference

## Basic Report

After running `sf dump`, generate a report of any missing files:

```
sfdump report-missing --export-dir exports/export-2026-01-25 --out missing_report
```

This creates:

- `missing_report.md` — Markdown report you can view in any text editor

## PDF Report

To generate a PDF (requires [Pandoc](https://pandoc.org) installed):

```
sfdump report-missing --export-dir exports/export-2026-01-25 --out missing_report --pdf
```

This creates both `missing_report.md` and `missing_report.pdf`.

## Redacted Reports

For reports you'll share externally or commit to a repository, use redaction:

```
sfdump report-missing --export-dir exports/export-2026-01-25 --out missing_report --redact
```

Redaction hides sensitive information:

| Hidden | Example |
|--------|---------|
| Salesforce IDs | `001xxx...xxx` → `[REDACTED]` |
| Filenames | `Contract_Acme.pdf` → `[REDACTED]` |
| URLs | Full Salesforce URLs removed |

Use redacted reports for external sharing. Keep full reports internal only.

## Report Contents

A typical report includes:

- **Summary** — Total files expected, downloaded, missing
- **Missing files list** — Details of files that couldn't be downloaded
- **Failure reasons** — Why each file failed (deleted, permissions, etc.)
- **Recommendations** — Next steps to resolve issues

## Example Workflow

```
# 1. Run export
sf dump

# 2. Generate internal report (full details)
sfdump report-missing --export-dir exports/export-2026-01-25 --out internal_report --pdf

# 3. Generate external report (redacted)
sfdump report-missing --export-dir exports/export-2026-01-25 --out external_report --redact --pdf
```

## Next Steps

- [Interpreting Reports](interpreting_reports.md) — Understanding report contents
- [FAQ](faq.md) — Common questions about exports and compliance
