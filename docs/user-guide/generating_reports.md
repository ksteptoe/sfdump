# Generating Reports

This page explains how to produce redacted or full audit reports.

## 1. Basic Report

```bash
sfdump report-missing   --export-dir exports/export-YYYY-MM-DD/files   --out docs/missing_report
```

This generates:

- `missing_report.md`
- Optional `missing_report.pdf` (requires pandoc)

## 2. Redacted Report

Safe for public docs or repo:

```bash
sfdump report-missing --export-dir ... --out docs/missing_report --redact
```

Redaction hides:

- Attachment IDs
- Parent IDs
- Filenames
- Salesforce URLs

## 3. Full Internal Report

```bash
sfdump report-missing   --export-dir ...   --out ../internal_reports/missing_report   --pdf
```

This includes:

- Full IDs
- Full filenames
- All URLs

Never commit internal reports.

## 4. Logo Support

If `src/logos/` contains a file, it is included automatically.

## 5. When to Generate Reports

- After retrying missing files
- Before IT/CFO review
- For audit trails
- For compliance certification
