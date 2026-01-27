# Installation

This guide explains how to install **sfdump** on your computer.

## Requirements

- **Windows 10 or 11** (recommended) — macOS and Linux also supported
- **40 GB+ free disk space** for Salesforce exports
- **Salesforce credentials** — contact your IT department for:
  - Connected App credentials (Client ID and Secret)
  - Your Salesforce username and password

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

1. Download sfdump to your home folder (`C:\Users\YourName\sfdump`)
2. Install Python if needed (no admin rights required)
3. Ask for your Salesforce credentials
4. Create a `.env` configuration file

Answer the prompts to complete setup.

### Troubleshooting

**"Running scripts is disabled"** — If you see this error, use this command instead:

```powershell
powershell -ExecutionPolicy Bypass -Command `
  "irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex"
```

**Already installed?** — The installer will detect existing installations and offer to update.

## macOS / Linux Installation

For macOS or Linux users:

```bash
curl -LO https://github.com/ksteptoe/sfdump/archive/refs/heads/main.zip
unzip main.zip
cd sfdump-main
make bootstrap
```

## Next Steps

Once installed, continue to [Getting Started](getting-started.md) for credential setup and your first export.
