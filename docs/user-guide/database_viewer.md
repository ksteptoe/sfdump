# Database Viewer

Browse your exported Salesforce data in an interactive web interface.

## Launching the Viewer

After running `sf dump`, launch the viewer:

```
sf view
```

This opens a web browser where you can:

- Search for records by name
- Navigate relationships (Account → Opportunity → Invoice)
- Find documents by Account or Opportunity
- Preview PDFs inline

The viewer automatically finds your most recent export.

## Opening a Specific Export

To view a specific export:

```
sf view ./exports/export-2026-01-15
```

## Viewer Interface

The viewer has a clean two-column layout:

| Area | Purpose |
|------|---------|
| **Left sidebar** | Object selector, search box, filters |
| **Left column** | Record details, relationships, documents |
| **Right column** | Document list and PDF preview |

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

## Finding Documents

### From a Record

Select any record and click the **Documents** tab to see:

- Documents attached to the current record
- Documents from parent records in your navigation path

**Example:** Viewing an Invoice shows documents from the Invoice, its parent Opportunity, and the parent Account.

### Document Explorer

The **Explorer** tab searches across ALL documents in your export.

**Search by invoice number (PIN/SIN):**
1. Click the **Explorer** tab
2. Type the invoice number in the Search box (e.g., "PIN010063")
3. Results show the record name first for easy identification

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

## Previewing Documents

Click any PDF to preview it in the right column:

- Multi-page PDFs scroll smoothly
- No download required
- Works for large files

For non-PDF files, you'll see a download link and file location.

## Common Tasks

### Find All Documents for a Customer

1. Click **Explorer** tab
2. Type the customer/account name
3. Review all related documents

### Review Invoices for a Deal

1. Select **Account** → search for customer
2. Navigate to **Children** → **Opportunities**
3. Open the specific opportunity
4. Navigate to **Children** → **Invoices**
5. Browse all invoices and attached documents

### Find a Specific Invoice

1. Select **Invoice** from the object dropdown
2. Search by invoice number (e.g., "SIN003926")
3. View details and attached documents

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
