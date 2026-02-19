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
- Install Python if needed (no admin rights required)
- Install sfdump from PyPI

After the installer finishes, run `sf setup` to configure your Salesforce credentials.

**If you see "Running scripts is disabled"**, use this command instead:

```powershell
powershell -ExecutionPolicy Bypass -Command `
  "irm https://raw.githubusercontent.com/ksteptoe/sfdump/main/bootstrap.ps1 | iex"
```

**To update later:** Run `sfdump upgrade` in PowerShell to upgrade to the latest version.

### Installing on macOS / Linux

```bash
pip install sfdump
```

---

## Step 2: Salesforce Setup

This is the most important step. You need credentials from your Salesforce administrator or IT department.

### What to Request from IT

Contact your Salesforce administrator and ask for **Connected App credentials** configured for the **Client Credentials OAuth flow**. They will provide:

| Credential | What It Looks Like | Example |
|------------|-------------------|---------|
| **Client ID** (Consumer Key) | Long alphanumeric string | `3MVG9_YOUR_CONSUMER_KEY_HERE` |
| **Client Secret** (Consumer Secret) | Long alphanumeric string | `YOUR_CONSUMER_SECRET_HERE` |
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
SF_CLIENT_ID=YOUR_CONSUMER_KEY_HERE
SF_CLIENT_SECRET=YOUR_CONSUMER_SECRET_HERE
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

### Home Screen

The viewer opens to a landing page with three viewers to choose from:

| Viewer | Purpose |
|--------|---------|
| **Object Viewer** | Browse any Salesforce object table — drill into records, explore parent/child relationships, and view attached documents |
| **HR Viewer** | View Contact records split by Employee and Contractor — search and filter people with key HR fields at a glance |
| **Finance Viewer** | Search and preview all exported documents — invoices, contracts, attachments — with built-in file preview |

Click a card to enter that viewer. Every viewer has a **Home** button to return to this landing page.

---

### Finance Viewer

The Finance Viewer is a full-width document search and preview tool.

**Searching for documents:**

1. Click **Finance Viewer** on the home screen
2. Type a customer name, invoice number (e.g. `SIN001234`), or keyword in the search box
3. Search supports glob wildcards — use `*` to match anything (e.g. `SIN001*`), `?` for a single character, or `[1-5]` for ranges
4. Tick **PDF Only** to limit results to PDF files
5. Expand **Additional Filters** to filter by Account Name, Opportunity Name, or Object Type

**Previewing and navigating:**

- Select a document from the results table to preview it inline (PDFs, images, emails, and more)
- Click **Open parent record** to jump directly to that record in the Object Viewer

Click **Home** (top-right) to return to the landing page.

---

### Object Viewer

The Object Viewer is a two-panel record browser with a sidebar for navigation.

**Sidebar controls:**

- **Object** — Choose a Salesforce object type (Account, Opportunity, Invoice, etc.)
- **Search** — Filter records by name or keyword (with optional regex)
- **Limit** — Control how many records to load (10–5,000)
- **Show all fields** / **Show Id columns** — Toggle field visibility

**Working with records:**

1. Click **Object Viewer** on the home screen
2. Select an object type from the sidebar
3. Click a record to see its details in three tabs:
   - **Details** — Field values for the selected record
   - **Children** — Related child records grouped by relationship (click **Open** to drill down)
   - **Documents** — Files attached directly to this record
4. The right panel shows a document tree for the selected record and its descendants, with depth and filter controls

**Navigation:**

- Clicking **Open** on a child record pushes it onto a breadcrumb trail in the sidebar
- Click any breadcrumb item to jump back, or use **Back** / **Reset** to navigate the trail
- Click **Home** in the sidebar to return to the landing page

---

### HR Viewer

The HR Viewer provides a focused view of Contact records, split by employment type.

The HR Viewer is password-protected because it contains sensitive personal data. The home screen shows a **Protected** label on the HR Viewer card. Contact your IT administrator for the password (administrators: see the [Security guide](../admin-guide/security.md)).

**Getting started:**

1. Click **HR Viewer** on the home screen
2. Enter the password provided by your IT department and click **Login**
3. Search by name using the search box (supports wildcards)
4. Optionally filter by region using the dropdown

**Browsing contacts:**

- Results are split into two tabs: **Employees** and **Contractors**, each showing a count
- Select a contact from the results and click **View Details** to see their full record
- Click **Back to list** to return to the search results

Click **Home** (top-right) to return to the landing page.

---

### Viewing Files

- PDFs and images display inline in the preview panel
- Click **Download** to save a copy to your computer
- Click **Open Folder** to see the file in your file explorer

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
