# Installation

This document explains how to install and configure **sfdump** for secure and complete Salesforce export workflows.

## Requirements

- Python 3.9+
- pip or uv
- Salesforce Connected App credentials
- API permissions to read:
  - Attachment
  - ContentVersion
  - Related business objects

## Install

```bash
pip install -e .
```

Or:

```bash
pip install sfdump
```

## Environment Variables

```bash
export SF_CLIENT_ID="xxx"
export SF_CLIENT_SECRET="yyy"
export SF_LOGIN_URL="https://login.salesforce.com"
export SF_AUTH_FLOW="client_credentials"
```

## Optional Tunables

- `SFDUMP_FILES_ORDER`
- `SFDUMP_FILES_CHUNK_TOTAL`
- `SFDUMP_FILES_CHUNK_INDEX`
- `SFDUMP_REDACT`
