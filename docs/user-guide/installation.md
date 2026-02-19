# Installation

This guide explains how to install **sfdump** on your computer.

## Requirements

- **Windows 10 or 11** (recommended) — macOS and Linux also supported
- **40 GB+ free disk space** for Salesforce exports
- **Salesforce credentials** — contact your IT department for:
  - Connected App credentials (Client ID and Secret)

## Windows Installation

### Step 1: Open PowerShell

1. Press the **Windows key** on your keyboard
2. Type **PowerShell**
3. Click on **Windows PowerShell** (the blue icon)

### Step 2: Run the Installer

Copy and paste this command into PowerShell, then press **Enter**:

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

### Step 3: Follow the Setup Wizard

The installer will:

1. Install Python if needed (no admin rights required)
2. Install sfdump from PyPI

After the installer finishes, run `sf setup` to configure your Salesforce credentials.

### Troubleshooting

**"Running scripts is disabled"** — If you see this error, use this command instead:

```powershell
powershell -ExecutionPolicy Bypass -Command `
  "irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex"
```

**To update later:** Run `pip install --upgrade sfdump` or `sfdump upgrade` in PowerShell.

## macOS / Linux Installation

For macOS or Linux users:

```bash
pip install sfdump
```

## Next Steps

Once installed, continue to [Getting Started](getting-started.md) for credential setup and your first export.
