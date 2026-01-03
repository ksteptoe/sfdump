# Database Viewer

The Database Viewer is an interactive web application for browsing Salesforce records, navigating relationships, and searching for documents. This is particularly valuable for organizations archiving data before shutdown.

## Overview

After exporting your Salesforce data, you can build a local SQLite database and browse it using a user-friendly web interface. The viewer provides:

- **Record browsing** - Search and view any Salesforce record
- **Relationship navigation** - Navigate from Accounts → Opportunities → Invoices → Documents
- **Document search** - Find documents by Account or Opportunity name
- **PDF preview** - View documents inline without downloading
- **Contextual messages** - Understand why certain data may be missing

## Prerequisites

Before using the database viewer, you must:

1. Complete a Salesforce export (see [Exporting Files](exporting_files.md))
2. Have Python 3.12+ installed
3. Install optional dependencies:
   ```bash
   pip install streamlit pymupdf pandas
   ```

## Building the Database

The first step is to convert your exported CSV files into a searchable SQLite database.

### Command

```bash
sfdump build-db -d exports/export-2025-12-31 --overwrite
```

**Parameters:**
- `-d, --export-dir`: Path to your export directory
- `--overwrite`: Replace existing database (optional)

**What it does:**
1. Reads all CSV files from the export directory
2. Creates tables for each Salesforce object (Account, Opportunity, Invoice, etc.)
3. Builds indexes on foreign key fields for fast relationship queries
4. Creates a master documents index for fast document search
5. Populates document paths for 100% coverage

**Output:**
```
SQLite viewer database created at exports/export-2025-12-31/meta/sfdata.db
```

**Database statistics:**
- Typical size: 200-500 MB for medium orgs
- Contains: All exported records + document metadata
- Location: `meta/sfdata.db` inside your export directory

### Verifying the Database

Check what's in your database:

```bash
sfdump db-info --db exports/export-2025-12-31/meta/sfdata.db
```

**Example output:**
```
Database: exports/export-2025-12-31/meta/sfdata.db
Size: 273 MB

Tables (20):
  account: 4,261 records
  opportunity: 2,442 records
  c2g__codaInvoice__c: 3,563 records
  c2g__codaPurchaseInvoice__c: 19,599 records
  record_documents: 22,653 documents
  ...
```

## Launching the Viewer

Once your database is built, launch the web-based viewer:

```bash
sfdump db-viewer --db exports/export-2025-12-31/meta/sfdata.db
```

**Output:**
```
Launching Streamlit viewer for exports/export-2025-12-31/meta/sfdata.db ...

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8503
  Network URL: http://192.168.1.249:8503
```

**What happens:**
1. Starts a local web server on port 8503
2. Opens your default web browser
3. Loads the interactive viewer interface

**Tips:**
- Leave the terminal window open - closing it stops the viewer
- Share the Network URL with others on your local network
- Press `Ctrl+C` in terminal to stop the viewer

## Viewer Interface Overview

The viewer has a clean, two-column layout designed for efficient navigation:

![Initial Viewer](Doc%20Pics/01-initial-viewer-account.png)
*Screenshot: Initial viewer showing Account object with clean layout*

**Layout:**
- **Left (40%)**: Record details & relationships
- **Right (60%)**: Documents section
- **Sidebar**: Navigation & search controls

### Left Sidebar - Navigation & Search

**Object Selector**
- Dropdown to select which Salesforce object to browse
- Common objects: Account, Opportunity, Contact, Invoice

**Search Box**
- Type any text to filter records
- Searches across all important fields (Name, Email, Title, etc.)
- Case-insensitive partial matching

**Filters**
- Limit: Number of records to display (default 100)
- Show all fields: Toggle detailed/compact view
- Show IDs: Display Salesforce IDs

### Left Column - Record Details & Relationships

Four tabs provide different views of the selected record:

1. **Details** - Important fields only (not all 100+ fields)
2. **Children** - Related child records with navigation controls
3. **Documents** - Files attached to this record
4. **Explorer** - Search across all documents

### Right Column - Documents

- **Recursive document search** from current record + all children
- **Parent document inclusion** from navigation chain
- **Record count** showing types and document count
- **Collapsible controls** for depth, filters
- **PDF preview** panel

## Browsing Records

### Selecting an Object

1. Click the **Object** dropdown in the sidebar
2. Select the object you want to browse (e.g., "Account")
3. Records load automatically
4. **The dropdown automatically syncs with navigation** - when you drill down to children, it updates

### Viewing Record Details

After selecting a record, the **Details** tab shows:

![Account Details](Doc%20Pics/02-account-details-important-fields.png)
*Screenshot: Account Details tab showing only important fields (7-10 key fields instead of 100+)*

**Key Features:**
- **Important fields only** by default - Name, Type, Industry, BillingCountry, Website, Phone
- **Compact display** - No more scrolling through 100+ fields
- **Toggle "Show all fields"** checkbox in sidebar to see everything
- **Expandable sections** - Parent fields grouped in expandable panel

**Field display:**
- Empty fields shown as "(empty)"
- Dates formatted for readability
- URLs clickable
- Long text fields word-wrapped

### Searching Records

**Search by name:**
1. In the sidebar search box, type part of the name (e.g., "VITEC")
2. Results filter as you type
3. Select a record to view details

**Example searches:**
- Account name: "VITEC" → finds all VITEC-related accounts
- Opportunity: "Degirum" → finds Degirum opportunities
- Invoice: "SIN003926" → finds specific invoice

**Note:** Search is automatically disabled when navigating to ensure the target record is always displayed.

## Navigating Relationships

The **Children** tab shows records related to the current record. This is how you navigate through your data hierarchy.

### Understanding Relationships

Salesforce data is interconnected:

```
Account
  └─ Opportunity (many)
      ├─ Opportunity Line Items (many)
      └─ Invoices (many)
          └─ Invoice Line Items (many)
```

### Viewing Child Records

1. Select a parent record (e.g., an Account)
2. Click the **Children** tab
3. Expand any relationship to see child records

![Children Navigation](Doc%20Pics/03-children-navigation.png)
*Screenshot: Children tab showing Opportunity relationship with navigation controls*

**Each relationship shows:**
- Relationship name (e.g., "Opportunity via AccountId")
- Child object type and field
- Number of records (e.g., "12 record(s)")
- **Navigation controls:** Dropdown + "Open" button

### Navigating Down

To drill down into a child record:

1. Expand a relationship section
2. Select a child record from the **"Select a child record"** dropdown
3. Click **"Open"** button
4. The viewer navigates to that child record

**What happens:**
- Page reloads showing the child record
- **Object dropdown syncs** to the new object type
- **Navigation breadcrumbs** appear in sidebar
- **Back** and **Reset** buttons become available

![Opportunity After Navigation](Doc%20Pics/04-opportunity-after-navigation.png)
*Screenshot: After navigating to Opportunity - Object dropdown auto-syncs, breadcrumbs appear*

### Contextual Messages

When viewing records with expected empty relationships, helpful messages explain why:

**Example: Closed Lost Opportunity with no invoices**

```
ℹ️ No invoices found. This is expected for Closed Lost opportunities
(Stage: Closed Lost), as they typically don't generate invoices.
```

This prevents confusion about "missing" data that's actually expected business logic.

### Multi-Level Navigation

You can navigate through multiple levels of relationships:

![Opportunity Children - Invoices](Doc%20Pics/05-opportunity-children-invoices.png)
*Screenshot: Opportunity Children tab showing Invoice relationship*

**Example navigation path:**
1. Start at Account: VITEC SA
2. Navigate to Opportunity: Vitec_Change_Order_CNN036
3. Navigate to Invoice: SIN003926

**Full breadcrumb trail maintains:**
- Account: VITEC SA
- Opportunity: Vitec_Change_Order_CNN036
- c2g__codaInvoice__c: SIN003926

### Parent Document Inclusion

**KEY FEATURE:** When viewing any record, the Documents section automatically includes files from all parent records in the navigation chain.

![Invoice with Parent Documents](Doc%20Pics/06-invoice-full-parent-chain.png)
*Screenshot: Invoice view showing full navigation chain (Account → Opportunity → Invoice) with documents from all parent records*

**Example:** Viewing invoice SIN003926 shows:
- Documents attached to the Invoice itself
- Documents attached to the parent Opportunity
- Documents attached to the parent Account

The record count displays: **"📊 4 records across 4 types │ 📄 2 documents"**

This eliminates the need to navigate back to parent records to find related documents!

## Document Explorer

The **Document Explorer** tab provides powerful search across all documents in your archive. This is critical for finding financial and contractual documents.

### Accessing Document Explorer

1. From any record, click the **Explorer** tab (rightmost tab in left column)
2. The Explorer provides a searchable table of ALL documents across the database

![Document Explorer](Doc%20Pics/07-document-explorer.png)
*Screenshot: Document Explorer tab showing searchable document table with filters*

### Search by Account

**To find all documents for an account:**

1. In "Account Name" field, type the account name (e.g., "VITEC")
2. Results update automatically
3. Shows all documents related to that account across all records

**Example:**
- Search: "VITEC"
- Results: All documents related to VITEC accounts and opportunities

### Search by Opportunity

**To find all documents for a specific deal:**

1. Type in the search/filter box to find opportunities by name
2. Results show all documents linked to matching opportunities

**Example:**
- Search: "Degirum"
- Results: All documents across Degirum opportunities

### Combined Search

You can combine multiple filters:

**Example: Find all VITEC PDFs from Q2 2020**
1. Account Name: "VITEC"
2. Opportunity Name: "Q2_2020"
3. Check "PDF first (only .pdf)"
4. Results: Specific PDFs for that deal

### Results Table

The results table shows key information:

| Column | Description |
|--------|-------------|
| `file_name` | Document filename |
| `file_extension` | .pdf, .docx, .xlsx, etc. |
| **`account_name`** | Which account it belongs to |
| **`opp_name`** | Which opportunity (if any) |
| `object_type` | What record type (Invoice, Opportunity, etc.) |
| `record_name` | Specific record name |
| `local_path` | File location in archive |

**Account and Opportunity columns** (highlighted) help you understand document context at a glance.

### Document Preview

The Documents section includes inline PDF preview (requires PyMuPDF):

**Features:**
- Multi-page PDFs scroll smoothly
- No download required
- Works for PDFs up to 50MB+

**Non-PDF files:**
- Download link provided
- File metadata shown
- Path to file location

## Common Workflows

### Workflow 1: Find All Documents for an Account

**Scenario:** Finance team needs all invoices and contracts for "VITEC SA"

**Steps:**
1. Launch viewer: `sfdump db-viewer --db exports/.../meta/sfdata.db`
2. Click **Document Explorer** tab
3. Type "VITEC" in **Account Name**
4. Check results (73 documents found)
5. Filter to PDFs only if needed
6. Preview or note file paths for extraction

**Time:** ~30 seconds

### Workflow 2: Navigate Account → Opportunity → Invoices

**Scenario:** Review all invoices for a specific deal

**Steps:**
1. Select **Account** object
2. Search for account name (e.g., "VITEC")
3. Click **Children** tab
4. Expand **Opportunity** relationship
5. Select desired opportunity, click **Open**
6. Click **Children** tab on Opportunity
7. Expand **Invoice** relationship
8. View all invoices for that deal

**Time:** ~1 minute

### Workflow 3: Find Missing Invoice Explanation

**Scenario:** Why does this Closed Lost opportunity have no invoices?

**Steps:**
1. Navigate to the Opportunity
2. Click **Children** tab
3. Expand **Invoice** relationship
4. Read contextual message explaining why it's empty

**Result:** Clear understanding without confusion

## Tips for Financial Users

### Finding Invoices

**All invoices for an account:**
- Document Explorer → Account Name: "[Account]"
- Filter to Invoice object type

**Specific invoice by number:**
- Select **Invoice** object
- Search for invoice number (e.g., "SIN002795")

**Invoice PDF:**
- Document Explorer → Search invoice number
- Preview PDF inline

### Finding Contracts/Agreements

**By account:**
- Document Explorer → Account Name
- Filter by file type: PDF or DOCX
- Look for filenames with "contract", "agreement", "RFP"

**By opportunity:**
- Document Explorer → Opportunity Name
- Often filed under opportunity records

### Understanding Amounts

**Opportunity amounts:**
- View Opportunity → Details tab → "Amount" field

**Invoice totals:**
- View Invoice → Details tab → Look for total/amount fields

**Related line items:**
- Children tab → Invoice Line Items
- Shows itemized details

## Troubleshooting

### Viewer Won't Start

**Error:** "Port 8503 already in use"

**Solution:**
```bash
# Kill any existing viewer
# Then restart
sfdump db-viewer --db exports/.../meta/sfdata.db
```

**Error:** "Database file not found"

**Solution:**
```bash
# Build the database first
sfdump build-db -d exports/export-2025-12-31 --overwrite
```

### No PDF Preview

**Message:** "Inline PDF preview requires PyMuPDF"

**Solution:**
```bash
pip install pymupdf
# Restart viewer
```

### Empty Results

**No documents found in search:**

Check:
1. Is the account/opportunity name spelled correctly?
2. Try partial match (e.g., "VIT" instead of "VITEC SA")
3. Uncheck "PDF first" to see all file types
4. Check if documents were exported (verify files/ directory)

**No child records:**

This may be expected:
- Closed Lost opportunities often have no invoices
- New accounts may have no opportunities
- Look for contextual messages explaining why

### Slow Performance

**Large database (>1GB):**
- Increase limit filter
- Use specific searches instead of browsing all
- Consider filtering export to essential objects

**Many documents (>50,000):**
- Document Explorer limited to 500 results
- Use specific Account/Opportunity searches
- Filter by file type to reduce results

## Next Steps

- **For end users:** See [Finding Documents](finding_documents.md) for simplified guide
- **For administrators:** See [Developer Guide](../developer-guide/index.md) for customization
- **For archive handoff:** See [FAQ](faq.md) for common questions

## Key Features Summary

The Database Viewer provides:
- ✅ **Default to Account object** - Starts with the most commonly used object
- ✅ **Compact field display** - Shows only 7-10 important fields instead of 100+
- ✅ **Smart navigation** - Object dropdown auto-syncs with navigation state
- ✅ **Breadcrumb trail** - Full navigation path with Back/Reset buttons
- ✅ **Parent document inclusion** - Automatically shows documents from navigation chain
- ✅ **Powerful document search** - Find files by Account/Opportunity across entire database
- ✅ **PDF preview** - View documents inline without downloads
- ✅ **Contextual help** - Explains why data may be missing

### Recent Improvements (2026-01)

- **Important Fields**: Reduced screen length by showing only key fields by default
- **Parent Documents**: When viewing Invoice, automatically includes Account + Opportunity documents
- **Navigation Sync**: Object dropdown stays in sync with breadcrumb navigation
- **Search Disable**: Search automatically disabled during navigation to ensure target record loads
- **Compact Layout**: Object details (40%) left, Documents (60%) right for optimal screen usage
- **Collapsible Controls**: Document search controls collapse to save space

This makes it ideal for archiving organizations before shutdown - providing permanent, offline access to critical business data with an intuitive, efficient interface.
