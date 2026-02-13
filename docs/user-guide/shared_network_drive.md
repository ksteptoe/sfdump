# Shared Network Drive Setup

This guide explains how to set up sfdump so that **multiple users** can browse the same Salesforce export using the viewer, with the exported data stored on a shared network drive.

## How It Works

Each user installs sfdump on their own PC and runs the viewer locally. The exported data (files and database) lives on a shared network drive that everyone can access. No server or Docker is needed.

```
Shared Drive (\\server\sfdump-export\)
├── files/           ← Downloaded Salesforce files
├── csv/             ← Exported object data
├── meta/
│   └── sfdata.db    ← SQLite database (viewer uses this)
└── indexes/         ← Search indexes
```

```
User A's PC                    User B's PC
┌─────────────┐                ┌─────────────┐
│ sfdump      │                │ sfdump      │
│ (installed  │──reads from──▶ │ (installed  │──reads from──▶
│  locally)   │  shared drive  │  locally)   │  shared drive
└─────────────┘                └─────────────┘
```

---

## Step 1: Run the Export (Admin Only)

One person (the admin) runs the full export. This only needs to happen once.

### Export to the Shared Drive

If the shared drive is already mapped (e.g., `S:\`):

```
sf dump -d S:\sfdump-export
```

Or export locally first, then copy:

```
sf dump -d ./exports/export-2026-01-26
```

Then copy the entire export folder to the shared drive:

```
xcopy /E /I exports\export-2026-01-26 S:\sfdump-export
```

### Verify the Database Exists

Check that the SQLite database was created:

```
dir S:\sfdump-export\meta\sfdata.db
```

If it doesn't exist, build it manually:

```
sfdump build-db -d S:\sfdump-export
```

---

## Step 2: Share the Export Folder

Make the export folder available on a network drive or shared folder that all users can access. Common options:

| Method | Example Path |
|--------|-------------|
| **Mapped network drive** | `S:\sfdump-export` |
| **UNC path** | `\\fileserver\shared\sfdump-export` |
| **OneDrive/SharePoint synced folder** | `C:\Users\Name\OneDrive - Company\sfdump-export` |

**Important:** Users need **read access** to the shared folder. Write access is not required for viewing.

---

## Step 3: Each User Installs sfdump

Each user installs sfdump on their own PC using the standard installer. They do **not** need Salesforce credentials — they only need sfdump installed to run the viewer.

### Windows Installation

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

See [Installation](installation.md) for details and troubleshooting.

### Skip Credential Setup

When the setup wizard asks for Salesforce credentials, users can **skip this step** — credentials are only needed for exporting data, not for viewing.

---

## Step 4: Launch the Viewer

Each user opens a terminal and runs:

```
sfdump db-viewer -d S:\sfdump-export
```

Replace `S:\sfdump-export` with whatever path the shared folder is at on their machine.

This opens a browser to `http://localhost:8501` where they can search records, browse relationships, and preview documents.

### Using a UNC Path

If the drive isn't mapped, use the full UNC path:

```
sfdump db-viewer -d "\\fileserver\shared\sfdump-export"
```

### Creating a Shortcut (Optional)

To make it easy for users, create a `.bat` file they can double-click:

1. Create a file called `View Salesforce Data.bat`
2. Add this content:

```batch
@echo off
cd /d %USERPROFILE%\sfdump
call .venv\Scripts\activate
sfdump db-viewer -d "S:\sfdump-export"
pause
```

3. Place it on the user's desktop or in the shared folder

---

## Updating the Export

When you need to refresh the data with a newer export:

1. Run a new export: `sf dump -d ./exports/export-2026-02-13`
2. Copy the new export to the shared drive, replacing the old data
3. Users restart their viewer to pick up the changes (Ctrl+C then re-run the command)

No reinstallation needed — users just restart the viewer.

---

## Troubleshooting

**"SQLite DB not found"**
- Check that `meta\sfdata.db` exists in the shared folder
- Run `sfdump build-db -d S:\sfdump-export` to rebuild it

**Viewer is slow**
- Network latency can affect performance when the database is on a remote drive
- For better performance, users can copy `meta\sfdata.db` to their local machine and use `sfdump db-viewer --db C:\local\sfdata.db` — but document preview will still need the shared drive for the actual files

**"Permission denied" errors**
- Verify the user has read access to the shared folder
- On Windows, check that the network drive is mapped or the UNC path is accessible

**Multiple users at the same time**
- Each user runs their own local Streamlit process, so there are no conflicts
- SQLite handles concurrent read access without issues
- Users do not interfere with each other

**Streamlit not installed**
- If users see "Streamlit is not installed", they need to activate their virtual environment first:
  ```
  cd %USERPROFILE%\sfdump
  .venv\Scripts\activate
  sfdump db-viewer -d S:\sfdump-export
  ```

## Tips

- **Read-only is fine** — the viewer never writes to the export folder
- **One export, many users** — any number of users can view the same data simultaneously
- **No Salesforce credentials needed** — users only need sfdump installed, not connected to Salesforce
- **Keep the terminal open** — closing the terminal stops the viewer
