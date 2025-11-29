# Quickstart

The fastest way to perform a full export and verify completeness.

## 1. Set Credentials

```bash
export SF_CLIENT_ID="xxx"
export SF_CLIENT_SECRET="yyy"
export SF_LOGIN_URL="https://login.salesforce.com"
```

## 2. Export

```bash
make -f Makefile.export export-files
```

## 3. Verify

```bash
sfdump verify-files --export-dir exports/export-YYYY-MM-DD/files
```

## 4. Retry

```bash
sfdump retry-missing --export-dir exports/export-YYYY-MM-DD/files -v
```

## 5. Generate Report

```bash
sfdump report-missing --export-dir exports/... --out docs/missing_report --redact
```
