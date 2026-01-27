# Installing sfdump on Windows

This guide is for users who are starting from scratch with nothing installed.

---

## Quick Install (Recommended)

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
- Download sfdump from GitHub
- Install Python (if needed)
- Set up everything automatically
- Guide you through configuration

---

## Manual Install (Alternative)

If the quick install doesn't work, follow these steps:

### Step 1: Download sfdump

1. Go to: **https://github.com/ksteptoe/sfdump**
2. Click the green **"Code"** button
3. Click **"Download ZIP"**
4. Save the file to your Downloads folder

### Step 2: Extract the ZIP file

1. Open your **Downloads** folder
2. Find **sfdump-main.zip**
3. Right-click on it
4. Select **"Extract All..."**
5. Choose where to extract (e.g., `C:\Users\YourName\sfdump`)
6. Click **Extract**

### Step 3: Run the installer

1. Open the extracted **sfdump-main** folder
2. Double-click **install.bat**
3. If Windows asks "Do you want to allow this app...?" click **Yes**
4. Follow the on-screen prompts

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

### Download fails or times out

Your network may block GitHub. Try:
1. Use a different network (e.g., mobile hotspot)
2. Download the ZIP manually (see Manual Install above)
3. Ask IT to whitelist `github.com` and `raw.githubusercontent.com`

### Installer window closes immediately

The installer hit an error. To see what went wrong:
1. Open PowerShell (see instructions above)
2. Navigate to the sfdump folder:
   ```powershell
   cd C:\Users\YourName\sfdump
   ```
3. Run the installer manually:
   ```powershell
   .\setup.ps1
   ```
4. The error message will stay visible

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

To update to the latest version:

1. Run `install.bat` again, or
2. Run the quick install command again - it will detect the existing installation and offer to update

---

## Uninstalling

1. Open the sfdump folder
2. Double-click `install.bat`
3. Choose option **4** (Uninstall)
4. Select what to remove:
   - **sfdump only** - keeps Python installed
   - **Complete removal** - removes Python too

Your data files (.env, exported files, databases) are **not deleted** automatically.
To remove everything, delete the sfdump folder after uninstalling.

---

## Getting Help

If you encounter issues:

1. Check the Troubleshooting section above
2. Report issues at: https://github.com/ksteptoe/sfdump/issues
