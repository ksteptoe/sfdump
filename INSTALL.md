# Installing sfdump

## Install from PyPI (All Platforms)

If you already have Python 3.12+ installed:

```bash
pip install sfdump
```

This works on Windows, macOS, and Linux.

---

## Windows (Starting from Nothing)

This section is for users who are starting from scratch with nothing installed.

---

### Quick Install (Recommended)

**Copy and paste this single command into PowerShell:**

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

### How to open PowerShell:

1. Press **Windows key + R** (opens Run dialog)
2. Type `powershell` and press **Enter**
3. A blue window will appear - this is PowerShell
4. Paste the command above (right-click to paste) and press **Enter**

The installer will:
- Install Python if needed (no admin rights required)
- Install sfdump from PyPI via `pip install sfdump`

After the installer finishes, run `sf setup` to configure your Salesforce credentials.

---

## What You'll Need

Before using sfdump, you'll need **Connected App credentials** from your Salesforce administrator:

| What to ask for | Where it goes |
|-----------------|---------------|
| Client ID (Consumer Key) | `SF_CLIENT_ID` in .env file |
| Client Secret (Consumer Secret) | `SF_CLIENT_SECRET` in .env file |
| Your Salesforce URL | `SF_LOGIN_URL` in .env file |

**Note:** sfdump uses OAuth Client Credentials flow — no username or password is needed. Ask your admin to set up a Connected App with Client Credentials authentication.

The installer will help you create and fill in the `.env` configuration file.

---

## System Requirements

- **Windows 10 or 11**
- **40 GB free disk space** (Salesforce exports can be large)
- **Internet connection** (to download and connect to Salesforce)
- **No administrator rights required** (installs for current user only)

---

## Troubleshooting

### "Python was not found" error

This happens when Windows has a Microsoft Store redirect enabled.

**Fix:**
1. Open **Settings** (Windows key + I)
2. Go to **Apps** > **Advanced app settings** > **App execution aliases**
3. Turn **OFF** both `python.exe` and `python3.exe`
4. Run the installer again

### "Running scripts is disabled on this system"

PowerShell has a security policy blocking scripts.

**Fix - run this command first:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```
Then run the installer again.

---

## After Installation

Once installed, you can use these commands:

| Command | What it does |
|---------|--------------|
| `sfdump --help` | Show all available commands |
| `sfdump login` | Test your Salesforce connection |
| `sfdump files` | Download Attachments and ContentVersions |
| `sfdump build-db` | Create a searchable database |
| `sfdump db-viewer` | Open the web viewer |

To run commands, open PowerShell or Command Prompt and type the command.

---

## Updating sfdump

```bash
pip install --upgrade sfdump
```

Or use the CLI:

```bash
sfdump upgrade
```

Your `.env` credentials and exported data are not affected.

---

## Uninstalling

```bash
pip uninstall sfdump
```

Your data files (.env, exported files, databases) are **not deleted** automatically.

---

## Getting Help

If you encounter issues:

1. Check the Troubleshooting section above
2. Report issues at: https://github.com/ksteptoe/sfdump/issues
