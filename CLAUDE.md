# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**sfdump** is a Salesforce data export and archival tool for bulk downloading Attachments and ContentVersions, with verification, retry mechanisms, searchable SQLite database creation, and a Streamlit web viewer.

## Build & Development Commands

### Setup
```bash
make bootstrap     # Install project with dev dependencies
make precommit     # Install pre-commit hooks (Ruff)
```

### Testing
```bash
make test          # Run cached unit + integration tests (stamped)
make test-all      # Run all non-live tests without caching
make test-live     # Run live tests (requires SF_LIVE_TESTS=true)
pytest tests/unit/test_api_client.py -v       # Run single test file
pytest tests/unit/test_api_client.py::test_function_name -v  # Run single test

# E2E tests (NOT run in CI - requires live Salesforce credentials)
SF_E2E_TESTS=true pytest tests/e2e/ -v
```

### Code Quality
```bash
make lint          # Run Ruff checks
make format        # Auto-fix with Ruff
make docs          # Build Sphinx docs to docs/_build/html
```

### Build & Release
```bash
make build         # Build wheel + sdist
make version       # Print setuptools_scm version
make run-cli       # Run CLI with CLI_ARGS=...
make release KIND=patch|minor|major  # Tag + GitHub Release with ZIP (requires gh CLI)
```

## Architecture

### Data Flow
```
Salesforce API → api.py → files.py → CSV + binary exports
                              ↓
                          verify.py (completeness)
                              ↓
                          retry.py (failures)
                              ↓
                          analyse.py (impact)
                              ↓
                          report.py (Markdown/PDF)
                              ↓
                     indexing/ (search indexes)
                              ↓
                    viewer/ + viewer_app/ (SQLite + Streamlit UI)
```

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| API Layer | `api.py`, `sf_auth.py` | Salesforce REST API with OAuth, retry logic |
| File Export | `files.py`, `export/` | Attachment/ContentVersion download with chunking |
| Orchestration | `dumper.py` | Central workflow coordinator |
| Verification | `verify.py`, `retry.py` | Completeness checking, failure retry |
| Reporting | `report.py`, `reports/` | Markdown/PDF with redaction support |
| Indexing | `indexing/` | Search index creation |
| Database | `viewer/db_builder.py` | SQLite database from CSV exports |
| Web UI | `viewer_app/` | Streamlit multi-page app |

### CLI Structure

Entry point: `src/sfdump/cli.py` (Click group) routing to `command_*.py` files

Key commands: `login`, `query`, `files`, `verify-files`, `retry-missing`, `analyze-missing`, `report-missing`, `build-db`, `db-viewer`, `schema`, `probe`, `csv`, `docs-index`

## Configuration

### Environment Variables (.env)
```env
SF_CLIENT_ID=<consumer_key>
SF_CLIENT_SECRET=<consumer_secret>
SF_HOST=login.salesforce.com
SF_USERNAME=user@example.com
SF_PASSWORD=<password+token>
SF_API_VERSION=v62.0  # optional
```

### Code Style
- Python 3.12+
- Line length: 100 (Ruff)
- Pre-commit hooks enforce formatting

## Testing

- **tests/unit/** - Mocked, fast tests
- **tests/integration/** - Fixture-based tests
- **tests/system/** - Live API tests (opt-in via `SF_LIVE_TESTS=true`)
- **tests/e2e/** - Full end-to-end tests with real Salesforce connection (opt-in via `SF_E2E_TESTS=true`)

Tests use stamped caching (SHA1 hashes) for incremental execution. Coverage omits UI/Streamlit code.

E2E tests verify the complete `sf dump` flow including:
- Full export pipeline (auth, files, CSV, indexes, database)
- Database integrity (tables, relationships, no duplicate IDs)
- File accessibility (paths in metadata point to actual files)

## Key Patterns

- All export operations are idempotent and support resume
- Chunking parameters (`SFDUMP_FILES_CHUNK_TOTAL`, `SFDUMP_FILES_CHUNK_INDEX`) handle API limits
- Reports support redaction via CLI flags for compliance
- SQLite database enables local querying without API calls

## Windows Installer

For non-technical Windows users, there's a menu-driven installer:

- `bootstrap.ps1` - One-liner install from GitHub (downloads latest release)
- `install.bat` / `setup.ps1` - Interactive setup with Python installation, disk space check, .env configuration
- Targets 40GB+ free disk space for Salesforce exports
- No admin rights required (per-user Python install)

