# Database Viewer

Browse your exported Salesforce data in an interactive web interface.

## Launching the Viewer

After running `sf dump`, launch the viewer:

```
sf view
```

This opens a web browser where you can:

- Search for documents by name, invoice number, or customer
- Navigate relationships (Account → Opportunity → Invoice)
- Preview documents inline (PDFs, images, spreadsheets, and more)

The viewer automatically finds your most recent export.

## Opening a Specific Export

To view a specific export:

```
sf view ./exports/export-2026-01-15
```

## Home Screen

The viewer opens to a landing page with three viewers to choose from:

| Viewer | Purpose |
|--------|---------|
| **Object Viewer** | Browse any Salesforce object table — drill into records, explore parent/child relationships, and view attached documents |
| **HR Viewer** | View Contact records split by Employee and Contractor — search and filter people with key HR fields at a glance |
| **Finance Viewer** | Search and preview all exported documents — invoices, contracts, attachments — with built-in file preview |

Click a card to enter that viewer. Every viewer has a **Home** button to return to this landing page.

## Finance Viewer

The Finance Viewer is a full-width document search and preview tool. This is where most users spend their time finding documents.

**Search by invoice number (PIN/SIN):**
1. Type the invoice number in the Search box (e.g., "SIN001234")
2. Results show the record name first for easy identification

**Using wildcards:**
- `SIN0016*` — finds SIN001600, SIN001601, etc.
- `SIN*` — finds all sales invoices
- `PIN0100[6-9]*` — finds a range (PIN01006x through PIN01009x)

Click **Search tips** for more wildcard examples.

**Additional filters (click to expand):**
- Filter by Account Name
- Filter by Opportunity Name
- Filter by Object Type

**Filter results:**
- Check "PDF only" to show only PDFs
- Results show record_name first, then file_name

**Navigating to records:**
- Click **Open parent record** on any search result to jump to that record in the Object Viewer

Click **Home** (top-right) to return to the landing page.

## Object Viewer

The Object Viewer has a sidebar and two-column layout for browsing records and their relationships:

| Area | Purpose |
|------|---------|
| **Sidebar** | Object selector, search box, filters, navigation breadcrumbs |
| **Left column** | Record list, record details, relationships, documents |
| **Right column** | Subtree document list and file preview |

### Selecting Records

1. Choose an object type from the dropdown (Account, Opportunity, Invoice, etc.)
2. Type in the search box to filter by name
3. Click a record to view its details

### Viewing Record Details

The **Details** tab shows important fields for the selected record:

- Account: Name, Industry, Website, Phone
- Opportunity: Name, Stage, Amount, Close Date
- Invoice: Number, Total, Status

Toggle "Show all fields" in the sidebar to see everything.

### Navigating Relationships

The **Children** tab shows related records. This is how you drill down through your data.

**Example navigation:**

1. Start at an Account (e.g., "Acme Corp")
2. Click **Children** tab → expand **Opportunities**
3. Select an Opportunity → click **Open**
4. Click **Children** tab → expand **Invoices**
5. View all invoices for that deal

**Navigation features:**

- **Breadcrumbs** — see your full path (Account → Opportunity → Invoice)
- **Back button** — return to previous record
- **Reset** — return to the starting point

### Documents Tab

Select any record and click the **Documents** tab to see:

- Documents attached to the current record
- Documents from parent records in your navigation path

**Example:** Viewing an Invoice shows documents from the Invoice, its parent Opportunity, and the parent Account.

## HR Viewer

The HR Viewer provides a focused view of Contact records, split by employment type.

The HR Viewer is password-protected because it contains sensitive personal data. The home screen shows a **Protected** label on the HR Viewer card.

**Getting started:**

1. Click **HR Viewer** on the home screen
2. Enter the password and click **Login**
3. Search by name using the search box (supports wildcards)
4. Optionally filter by region using the dropdown

**Browsing contacts:**

- Results are split into two tabs: **Employees** and **Contractors**, each showing a count
- Select a contact from the results and click **View Details** to see their full record
- Click **Back to list** to return to the search results

**Password management:** See the [Administrators Guide — Security](../admin-guide/security.md) for how to set, change, and remove the HR Viewer password.

Click **Home** (top-right) to return to the landing page.

## Previewing Documents

Click any document to preview it. The viewer supports inline preview for many file types:

| File type | Preview |
|-----------|---------|
| **PDF** | Multi-page inline preview with smooth scrolling |
| **Images** (JPG, PNG, GIF, BMP, TIFF, JFIF) | Inline image preview |
| **Excel** (XLSX, XLS, XLTX, XLSM) | Table preview with sheet selection |
| **CSV / TSV** | Table preview |
| **HTML / HTM** | Source preview |
| **EML emails** (.eml) | Headers and body preview |
| **Outlook emails** (.msg) | Headers and body preview |
| **Text files** | Code-style preview |
| **Other files** (.docx, .pptx, .zip, etc.) | Download button |

All previewable file types also include a download button.

## Common Tasks

### Find All Documents for a Customer

1. Open **Finance Viewer** from the home screen
2. Type the customer/account name in the Search box
3. Review all related documents

### Review Invoices for a Deal

1. Open **Object Viewer** from the home screen
2. Select **Account** → search for customer
3. Navigate to **Children** → **Opportunities**
4. Open the specific opportunity
5. Navigate to **Children** → **Invoices**
6. Browse all invoices and attached documents

### Find a Specific Invoice

1. Open **Finance Viewer** from the home screen
2. Type the invoice number in the Search box (e.g., "SIN001234")
3. Click **Open parent record** to view the full invoice details in Object Viewer

## Tips

- **Search is case-insensitive** — "acme" finds "Acme Corp"
- **Partial matches work** — "beta" finds "Beta Industries Ltd"
- **Documents include parents** — viewing a child record shows parent documents too
- **Empty relationships are explained** — contextual messages explain why data may be missing

## Troubleshooting

**Viewer won't start:**
- Make sure you've run `sf dump` first
- Check that the export directory exists

**No documents found:**
- Try a partial name match
- Uncheck "PDF only" to see all file types
- Verify files were exported (check `files/` directory)

**Slow performance with large exports:**
- Use specific searches instead of browsing all records
- Filter by object type or file type

## Next Steps

- [Finding Documents](finding_documents.md) — Simplified guide for end users
- [FAQ](faq.md) — Common questions
