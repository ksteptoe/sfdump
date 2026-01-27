# Getting Started

This guide walks you through installing sfdump, connecting to Salesforce, running your first export, and viewing your data. No technical experience required.

**Time required:** 15-20 minutes (plus export time, which varies by data size)

---

## Step 1: Installation

### What You Need

Before starting, make sure you have:

- **Windows 10 or 11** (macOS and Linux also supported)
- **40 GB+ free disk space** for your Salesforce export
- **Salesforce credentials** from your IT department (see Step 2)

### Installing on Windows

1. Press the **Windows key** on your keyboard
2. Type **PowerShell**
3. Click on **Windows PowerShell** (the blue icon)
4. Copy and paste this command, then press **Enter**:

```powershell
irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex
```

The installer will:
- Download sfdump to your home folder (`C:\Users\YourName\sfdump`)
- Install Python if needed (no admin rights required)
- Guide you through credential setup

**If you see "Running scripts is disabled"**, use this command instead:

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex"
```

### Installing on macOS / Linux

```bash
curl -LO https://github.com/ksteptoe/sfdump/archive/refs/heads/main.zip
unzip main.zip
cd sfdump-main
make bootstrap
```

---

## Step 2: Salesforce Setup

This is the most important step. You need credentials from your Salesforce administrator or IT department.

### What to Request from IT

Contact your Salesforce administrator and ask for **Connected App credentials** configured for the **Client Credentials OAuth flow**. They will provide:

| Credential | What It Looks Like | Example |
|------------|-------------------|---------|
| **Client ID** (Consumer Key) | Long alphanumeric string | `3MVG9...vvxeVcp` |
| **Client Secret** (Consumer Secret) | Long alphanumeric string | `D6BE...CF8091` |
| **Login URL** | Your Salesforce instance URL | `https://yourcompany.my.salesforce.com` |

**Note:** This uses OAuth Client Credentials flow — no username or password is required. Your IT department configures the Connected App to authenticate directly.

### Running Setup

Once you have your credentials, open a terminal and run:

```
sf setup
```

You'll be prompted to enter each credential. The setup wizard saves them to a `.env` file.

**What the .env file looks like:**

```
SF_AUTH_FLOW=client_credentials
SF_CLIENT_ID=3MVG9...your_client_id...
SF_CLIENT_SECRET=D6BE...your_client_secret...
SF_LOGIN_URL=https://yourcompany.my.salesforce.com
SF_API_VERSION=v60.0
```

### Test Your Connection

Verify everything is configured correctly:

```
sf test
```

**Success looks like this:**

```
Testing Salesforce Connection
==================================================
Config: C:\Users\YourName\sfdump\.env

Connecting... OK
Instance: https://yourcompany.my.salesforce.com
Testing query... OK

Connection successful! Ready to export.
```

### Common Setup Problems

| Error | Solution |
|-------|----------|
| `SF_CLIENT_ID not set` | Run `sf setup` to enter your credentials |
| `SF_LOGIN_URL not set` | Add your Salesforce instance URL to `.env` |
| `Invalid client credentials` | Double-check Client ID and Client Secret with IT |
| `Token request failed (400)` | Verify the Connected App is configured for Client Credentials flow |
| `Token request failed (401)` | Client ID or Secret is incorrect |
| `Connection failed` | Check your network connection and verify `SF_LOGIN_URL` is correct |

**Still stuck?** Ask your IT department to verify:
1. The Connected App is configured for **Client Credentials** OAuth flow
2. The app has the required API permissions (e.g., `api`, `refresh_token`)
3. A "run as" user is configured with appropriate Salesforce data access

---

## Step 3: Export Your Data (sf dump)

Now you're ready to download your Salesforce files and data.

### Running the Export

```
sf dump
```

This command automatically:

1. Authenticates to Salesforce using your credentials
2. Downloads all Attachments and ContentVersions (files)
3. Exports business data (Accounts, Contacts, Opportunities, etc.)
4. Builds searchable indexes for fast lookups
5. Creates a SQLite database for offline browsing
6. Verifies all downloads and retries any failures

### What to Expect

The export runs through several stages. You'll see progress updates:

```
==================================================
sfdump - Salesforce Data Export
==================================================

Step 1/6: Authenticating...
  Connected to: https://yourcompany.my.salesforce.com

Step 2/6: Querying file metadata...
  Found 12,479 files to download

Step 3/6: Downloading files...
  [################################] 12,456 / 12,479 (99.8%)

Step 4/6: Exporting object data...
  Account: 2,341 records
  Contact: 8,127 records
  Opportunity: 1,892 records
  ... (more objects)

Step 5/6: Building indexes...
  Creating search indexes...

Step 6/6: Creating database...
  Database ready: ./exports/export-2026-01-26/meta/sfdata.db
```

**How long does it take?**

This depends on your data size:
- Small org (< 1,000 files): A few minutes
- Medium org (1,000-10,000 files): 15-60 minutes
- Large org (10,000+ files): Several hours

You can leave it running and check back later.

### What Success Looks Like

When complete, you'll see a summary:

```
==================================================
Export Summary
==================================================

  Location:    ./exports/export-2026-01-26

  Files
    Expected:    12,479
    Downloaded:  12,456
    Missing:     23
    Complete:    99.8%

  NEARLY COMPLETE - 23 files could not be retrieved
  (These may have been deleted from Salesforce)

  Objects:  38
  Database: ./exports/export-2026-01-26/meta/sfdata.db

  To browse your data:
    sf view
```

**Understanding the summary:**

| Metric | Meaning |
|--------|---------|
| **Downloaded** | Files successfully saved to your computer |
| **Missing** | Files that no longer exist in Salesforce (normal) |
| **Complete %** | 99%+ is excellent; 100% is rare due to normal deletions |

**Note:** A 99%+ completion rate is normal and expected. Some files in Salesforce metadata may have been deleted but their records remain. This is not an error.

### If Something Goes Wrong

**Export interrupted?** Just run `sf dump` again. It automatically resumes where it left off and retries any failed downloads.

**Completion below 95%?** This might indicate a connection issue. Run `sf dump` again — it will retry failed downloads.

### Custom Export Location

By default, exports are saved to `./exports/export-YYYY-MM-DD/`. To specify a different location:

```
sf dump -d /path/to/my-export
```

---

## Step 4: View Your Data (sf view)

Once the export completes, you can browse your data in a web interface.

### Launch the Viewer

```
sf view
```

This opens your web browser to the sfdump viewer (usually at `http://localhost:8501`).

**Keep the terminal window open** — closing it stops the viewer.

### Finding Documents

1. Click the **Explorer** tab in the sidebar
2. Type a customer name, project name, or keyword in the search box
3. Results show matching Accounts, Contacts, Opportunities, and files
4. Click any result to see details and related documents

### Browsing by Account

1. Go to **Accounts** in the sidebar
2. Scroll or search for the account you want
3. Click an account to see:
   - Account details
   - Related Contacts
   - Related Opportunities
   - Attached files and documents

### Viewing Files

- Click any file name to preview it
- PDFs and images display inline
- Click **Download** to save a copy to your computer
- Click **Open Folder** to see the file in Windows Explorer

### Closing the Viewer

To stop the viewer, go back to your terminal and press **Ctrl+C**.

---

## Quick Reference

| Command | What It Does |
|---------|--------------|
| `sf setup` | Configure Salesforce credentials |
| `sf test` | Verify connection works |
| `sf dump` | Export everything from Salesforce |
| `sf view` | Browse exported data in web viewer |
| `sf status` | List available exports |

---

## Next Steps

- [Finding Documents](finding_documents.md) — Advanced search tips and techniques
- [FAQ](faq.md) — Common questions answered

---

## Need Help?

**Connection issues:** Run `sf test` and check the error message against the troubleshooting table above.

**Credential problems:** Contact your IT department to verify your Connected App access.

**Export questions:** See the [FAQ](faq.md) for common scenarios.
