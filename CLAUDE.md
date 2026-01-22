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

Tests use stamped caching (SHA1 hashes) for incremental execution. Coverage omits UI/Streamlit code.

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

## PENDING: Git History Cleanup for Public Release

**Status:** Current HEAD is sanitized, but git history still contains sensitive data.

### What Was Already Done (commit 8a64095)
- Deleted 12 screenshots containing real customer data (VITEC, ST Microelectronics)
- Deleted `docs/Database_Viewer_Guide.pdf` with embedded sensitive screenshots
- Removed all references to: `Example Company`, `yourorg.my.salesforce.com`, `EXAMPLE CORP`
- Sanitized customer names: VITEC → Acme Corp, Degirum → Beta Industries
- Replaced personal paths (`C:/Users/kevin/OneDrive - Example Company/SF`) with generic paths

### What Still Needs to Be Done
Rewrite git history to remove sensitive data from ALL commits, not just HEAD.

### Sensitive Patterns to Remove from History

**Files to delete from all history:**
```
docs/_static/viewer/*.png
docs/doc-pics/*.png
docs/Database_Viewer_Guide.pdf
```

**Text patterns to scrub:**
- `YourOrg` (company name)
- `yourorg.my.salesforce.com` (Salesforce instance)
- `EXAMPLE CORP` / `EXAMPLE-CORP` / `Example Corp` (company name)
- `OneDrive - Example Company` (personal paths)
- `example.com` (email domain in commits)

### Instructions for git-filter-repo

1. **Install git-filter-repo:**
   ```bash
   pip install git-filter-repo
   ```

2. **Create a fresh clone (required by git-filter-repo):**
   ```bash
   cd ..
   git clone --mirror https://github.com/ksteptoe/sfdump.git sfdump-mirror
   cd sfdump-mirror
   ```

3. **Remove sensitive files from history:**
   ```bash
   git filter-repo --path-glob 'docs/_static/viewer/*.png' --invert-paths
   git filter-repo --path-glob 'docs/doc-pics/*.png' --invert-paths
   git filter-repo --path docs/Database_Viewer_Guide.pdf --invert-paths
   ```

4. **Replace sensitive text patterns:**
   Create a file `replacements.txt`:
   ```
   Example Company==>Example Company
   YourOrg==>YourOrg
   yourorg.my.salesforce.com==>yourorg.my.salesforce.com
   EXAMPLE CORP==>EXAMPLE CORP
   EXAMPLE-CORP==>EXAMPLE-CORP
   Example Corp==>Example Corp
   OneDrive - Example Company==>sfdump-exports
   example.com==>example.com
   ```

   Then run:
   ```bash
   git filter-repo --replace-text replacements.txt
   ```

5. **Force push to GitHub:**
   ```bash
   git push --force --all
   git push --force --tags
   ```

6. **Important:** After force push, all collaborators must re-clone the repo.

### Alternative: BFG Repo-Cleaner

If git-filter-repo is unavailable:
```bash
# Download BFG
curl -L -o bfg.jar https://repo1.maven.org/maven2/com/madgag/bfg/1.14.0/bfg-1.14.0.jar

# Remove files
java -jar bfg.jar --delete-files '*.png' --no-blob-protection sfdump.git
java -jar bfg.jar --delete-files 'Database_Viewer_Guide.pdf' sfdump.git

# Replace text (create passwords.txt with patterns)
java -jar bfg.jar --replace-text passwords.txt sfdump.git

# Cleanup and push
cd sfdump.git
git reflog expire --expire=now --all && git gc --prune=now --aggressive
git push --force
```

### Verification After Cleanup

Run these searches to verify history is clean:
```bash
git log --all -p -S "YourOrg" | head -50
git log --all -p -S "VITEC" | head -50
git log --all -p -S "yourorg.my.salesforce.com" | head -50
git log --all -p -S "AION" | head -50
```

All should return empty results.
