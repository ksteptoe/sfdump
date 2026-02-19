# Deployment

This guide covers installing and maintaining sfdump in production environments.

---

## Installation

### All Platforms (PyPI)

```bash
pip install sfdump
```

Requires Python 3.12+. This installs the `sfdump` and `sf` commands.

### Windows (Non-Technical Users)

For users who may not have Python installed, a bootstrap script handles everything:

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

This will:
1. Install Python if needed (per-user, no admin rights)
2. Install sfdump from PyPI via `pip install sfdump`

After installation, the user runs `sf setup` to configure Salesforce credentials.

### Verifying Installation

```bash
sfdump --version
sf --version
sf test               # requires .env with credentials
```

---

## Upgrading

```bash
pip install --upgrade sfdump
```

Or use the built-in command:

```bash
sfdump upgrade
```

The viewer shows an upgrade banner when a newer version is available on PyPI.

Upgrades do not affect exported data, databases, or `.env` credentials.

---

## Database Rebuilds

After an export, the SQLite database can be rebuilt at any time:

```bash
sfdump build-db -d exports/export-2026-01-26
```

To rebuild and set the HR Viewer password in one step:

```bash
sfdump build-db -d exports/export-2026-01-26 --hr-password
```

Use `--overwrite` to replace an existing database.

The database is derived entirely from the CSV and metadata files in the export directory. Rebuilding is safe and idempotent.

---

## Scheduled Exports

sfdump is designed for automated, unattended exports:

```bash
sf dump
```

Key properties:
- **Idempotent** — re-running skips already-downloaded files
- **Resumable** — interrupted exports continue from where they stopped
- **Chunking** — split large exports across multiple runs:

```bash
export SFDUMP_FILES_CHUNK_TOTAL=4
export SFDUMP_FILES_CHUNK_INDEX=1    # run 1 of 4
sf dump
```

### Windows Task Scheduler

1. Create a new task
2. Set the action to run: `sf dump`
3. Set the working directory to your sfdump folder (where `.env` is located)
4. Schedule as needed (e.g. weekly)

### Linux / macOS Cron

```cron
0 2 * * 0  cd /path/to/sfdump && sf dump >> /var/log/sfdump.log 2>&1
```

---

## Export Completeness

After an export, verify completeness:

```bash
sf inventory
```

This checks six categories: CSV Objects, Attachments, ContentVersions, Invoice PDFs, Indexes, and Database. The result is also written to `meta/inventory.json`.

For CI pipelines:

```bash
sf inventory --json-only
```

---

## Uninstalling

```bash
pip uninstall sfdump
```

This removes the sfdump package. Exported data, databases, and `.env` files are not affected.

To remove everything, also delete:
- The export directory (e.g. `exports/`)
- The `.env` file
- Any SQLite databases
