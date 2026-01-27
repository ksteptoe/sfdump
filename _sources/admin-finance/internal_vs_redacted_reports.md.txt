# Internal vs Redacted Reports

## Internal Reports

Contain:

- Full IDs
- Filenames
- Salesforce URLs

Must be stored outside Git.

## Redacted Reports

Contain:

- ATTACHMENT_n
- PARENT_n
- [REDACTED] filenames

Safe for:

- Sphinx docs
- Partner communication
- General distribution

## How to Generate

Internal:

```bash
sfdump report-missing --out ../internal_reports/... --pdf
```

Redacted:

```bash
sfdump report-missing --out docs/missing_report --redact
```
