# Finding Documents

**For:** Finance teams, accountants, contract managers, and anyone who needs to find documents quickly.

This guide assumes **zero technical background**. If you can use a web browser, you can find documents.

## Opening the Viewer

Run this command:

```
sf view
```

Your web browser opens automatically with the document viewer. The search page appears immediately — you can start searching right away.

**Tip:** Keep the terminal window open — closing it stops the viewer.

## Finding Documents by Invoice Number (PIN/SIN)

This is the most common task for finance users.

1. Type the invoice number in the **Search** box (e.g., "PIN010063" or "SIN001234")
2. Results appear automatically as you type

**Results show:**

| Column | Meaning |
|--------|---------|
| record_name | Invoice/record number (e.g., "PIN010063") |
| file_name | Document name (e.g., "Invoice_2024.pdf") |
| account_name | Customer name |
| opp_name | Deal/project name |

## Using Wildcards

The search box supports wildcards for powerful searching:

| Pattern | Meaning | Example |
|---------|---------|---------|
| `*` | Any characters | `PIN01006*` finds PIN010060, PIN010061, etc. |
| `?` | Single character | `PIN01006?` finds PIN010060 to PIN010069 |
| `[1-5]` | Range of characters | `PIN0100[6-9]*` finds PIN01006x through PIN01009x |

**Examples:**
- `SIN*` — all sales invoices
- `PIN01*` — all purchase invoices starting with PIN01
- `*Acme*` — anything containing "Acme"

Click **Search tips** below the search box for more examples.

## Finding Documents by Customer Name

1. Click **Additional Filters** to expand
2. Type the customer name in the **Account Name** box (e.g., "Acme Corp")
3. Results show all documents for that customer

## Finding Documents by Deal Name

If you know the project or opportunity name:

1. Click **Additional Filters** to expand
2. Type the deal name in the **Opportunity Name** box
3. Results show all documents for that deal

**Combined search:** Use multiple filters together to narrow results.

## Finding a Specific Invoice

**Method 1: By invoice number (fastest)**
1. Type the invoice number in the Search box (e.g., "SIN001234")
2. Click the invoice to view details

**Method 2: Through customer**
1. Click Additional Filters → type customer name
2. Look for invoices in the results

## Finding Contracts

1. Type keywords like "contract", "agreement", or "SOW"
2. Check **"PDF only"** — contracts are usually PDFs
3. Or search by customer name in Additional Filters

## Previewing Documents

Click any document to preview it directly in the browser:

| File type | What you see |
|-----------|-------------|
| **PDF** | Multi-page preview with smooth scrolling |
| **Images** (JPG, PNG, GIF, BMP, TIFF, JFIF) | Inline image |
| **Excel** (XLSX, XLS) | Table with sheet selection |
| **CSV / TSV** | Table preview |
| **HTML / EML emails** | Content preview |
| **Outlook emails** (.msg) | Headers and body preview |
| **Text files** | Code-style preview |
| **Other files** (.docx, .zip, etc.) | Download button |

No download required for most file types — everything previews in the browser.

## Selecting Documents from Results

After searching, use the **Select a document** dropdown:

- Documents show as: `001 — PIN010063 | invoice_filename.pdf`
- The record name (PIN/SIN) appears first for easy identification
- Click to preview the document

## Viewing the Parent Record

After finding a document, you can view the full record it belongs to:

1. Click **Open parent record** below the search results
2. This switches to DB Viewer mode showing the record's details, relationships, and all attached documents
3. Click **Back to Explorer** in the sidebar to return to search

## Common Tasks

### All invoices for a customer

1. Click Additional Filters → Account Name: [customer name]
2. Review all attached documents

### All documents for a deal

1. Click Additional Filters → Opportunity Name: [deal name]
2. Review all attached documents

### Purchase invoices (bills) in a range

1. Search: `PIN0100[6-9]*`
2. This finds PIN01006x through PIN01009x

### All PDFs containing a keyword

1. Search: `*keyword*`
2. Check "PDF only"

## Understanding the Data

### Account vs Opportunity vs Invoice

| Term | Meaning | Example |
|------|---------|---------|
| **Account** | Customer company | "Acme Corp" |
| **Opportunity** | Specific deal or project | "Acme Corp Q2 2024" |
| **Invoice** | Billing document | "SIN001234" |
| **Purchase Invoice** | Bill from supplier | "PIN010063" |

### Why some records have no documents

You might see: *"No invoices found. This is expected for Closed Lost opportunities."*

This is normal — it means:
- The deal didn't happen, so no invoice was created
- Or documents were never uploaded to Salesforce

This doesn't mean data is lost.

## Tips

- **Partial names work** — "Acme" finds "Acme Corp SA"
- **Case doesn't matter** — "acme" = "ACME" = "Acme"
- **Use wildcards** — `PIN*` finds all purchase invoices
- **Too many results?** — Check "PDF only" or use more specific search terms
- **Can't find something?** — Try wildcard search like `*keyword*`

## Troubleshooting

**"No matches found"**
- Check spelling
- Try wildcards: `*partial*`
- Uncheck "PDF only"

**Viewer not loading**
- Make sure terminal is still open
- Run `sf view` again

**Can't find a document**
- Try wildcard search: `*filename*`
- Try searching by customer name in Additional Filters
- Document might be attached to a different record

## Quick Reference

| Task | Steps |
|------|-------|
| Find by invoice number | Search → type `PIN010063` |
| Find invoice range | Search → type `PIN0100[6-9]*` |
| Find customer documents | Additional Filters → Account Name |
| Find deal documents | Additional Filters → Opportunity Name |
| Preview document | Click document in results |
| View parent record | Click "Open parent record" |

**You don't need technical skills — just type and click!**
