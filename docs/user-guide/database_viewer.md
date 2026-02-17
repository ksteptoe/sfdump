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

## Two Views

The viewer has two modes you can switch between:

| View | Purpose | Default? |
|------|---------|----------|
| **Explorer** | Full-width document search across all exported files | Yes (landing page) |
| **DB Viewer** | Record browser with sidebar controls and relationship navigation | No (click "DB Viewer" button) |

### Switching Between Views

- **Explorer → DB Viewer**: Click the **DB Viewer** button in the top-right corner
- **DB Viewer → Explorer**: Click **Back to Explorer** at the top of the sidebar
- **Explorer → DB Viewer (via record)**: Click **Open parent record** on any search result to jump to that record in DB Viewer

## Explorer (Default View)

The Explorer is a full-width document search with no sidebar. This is where most users spend their time.

**Search by invoice number (PIN/SIN):**
1. Type the invoice number in the Search box (e.g., "PIN010063")
2. Results show the record name first for easy identification

**Using wildcards:**
- `PIN01006*` — finds PIN010060, PIN010061, etc.
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

## DB Viewer

The DB Viewer has a sidebar and two-column layout for browsing records and their relationships:

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

## Navigating Relationships

The **Children** tab (in DB Viewer) shows related records. This is how you drill down through your data.

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

## Finding Documents

### From the Explorer

The easiest way to find documents — just search:

1. Type a customer name, invoice number, or keyword
2. Results show all matching documents across the entire export
3. Click any result to preview it

### From a Record (DB Viewer)

Select any record in DB Viewer and click the **Documents** tab to see:

- Documents attached to the current record
- Documents from parent records in your navigation path

**Example:** Viewing an Invoice shows documents from the Invoice, its parent Opportunity, and the parent Account.

### Jumping Between Views

When viewing a document in Explorer, click **Open parent record** to jump to DB Viewer with that record selected. This lets you explore the record's relationships and other attached documents.

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

1. Type the customer/account name in the Search box
2. Review all related documents

### Review Invoices for a Deal

1. Click **DB Viewer** to switch to record browser
2. Select **Account** → search for customer
3. Navigate to **Children** → **Opportunities**
4. Open the specific opportunity
5. Navigate to **Children** → **Invoices**
6. Browse all invoices and attached documents

### Find a Specific Invoice

1. Type the invoice number in the Search box (e.g., "SIN001234")
2. Click **Open parent record** to view the full invoice details in DB Viewer

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
