# Finding Documents

**For:** Finance teams, accountants, contract managers, and anyone who needs to find documents quickly.

This guide assumes **zero technical background**. If you can use a web browser, you can find documents.

## Opening the Viewer

Run this command:

```
sf view
```

Your web browser opens automatically with the document viewer.

**Tip:** Keep the terminal window open — closing it stops the viewer.

## Finding Documents by Customer Name

This is the most common task.

1. Click the **Explorer** tab
2. Type the customer name in the **Account Name** box (e.g., "Acme Corp")
3. Results appear automatically as you type

**What you'll see:**

| Column | Meaning |
|--------|---------|
| file_name | Document name (e.g., "Invoice_2024.pdf") |
| account_name | Customer name |
| opp_name | Deal/project name |
| object_type | Record type (Invoice, Opportunity, etc.) |

## Finding Documents by Deal Name

If you know the project or opportunity name:

1. Click the **Explorer** tab
2. Type the deal name in the **Opportunity Name** box
3. Results show all documents for that deal

**Combined search:** Type both Account and Opportunity names to narrow results.

## Finding a Specific Invoice

**Method 1: By invoice number**
1. Select **Invoice** from the Object dropdown (sidebar)
2. Type the invoice number (e.g., "SIN002795")
3. Click the invoice to view details

**Method 2: Through customer**
1. Explorer tab → type customer name
2. Look for invoices in the results

## Finding Contracts

1. Click **Explorer** tab
2. Type the customer name
3. Check **"PDF only"** — contracts are usually PDFs
4. Look for filenames containing:
   - "Contract"
   - "Agreement"
   - "SOW" (Statement of Work)
   - "MSA" (Master Service Agreement)

## Previewing Documents

Click any PDF to preview it:

- Multi-page documents scroll smoothly
- No download required
- Works directly in the browser

For non-PDF files, you'll see the file location to access directly.

## Common Tasks

### All invoices for a customer

1. Explorer tab
2. Account Name: [customer name]
3. Filter to Invoice type if needed

### All documents for a deal

1. Explorer tab
2. Opportunity Name: [deal name]
3. Review all attached documents

### Purchase invoices (bills)

1. Select **Purchase Invoice** from Object dropdown
2. Search by vendor name or invoice number

## Understanding the Data

### Account vs Opportunity vs Invoice

| Term | Meaning | Example |
|------|---------|---------|
| **Account** | Customer company | "Acme Corp" |
| **Opportunity** | Specific deal or project | "Acme Corp Q2 2024" |
| **Invoice** | Billing document | "SIN002795" |

### Why some records have no documents

You might see: *"No invoices found. This is expected for Closed Lost opportunities."*

This is normal — it means:
- The deal didn't happen, so no invoice was created
- Or documents were never uploaded to Salesforce

This doesn't mean data is lost.

## Tips

- **Partial names work** — "Acme" finds "Acme Corp SA"
- **Case doesn't matter** — "acme" = "ACME" = "Acme"
- **Too many results?** — Check "PDF only" or add more search terms
- **Can't find something?** — Try searching by customer instead of deal name

## Troubleshooting

**"No matches found"**
- Check spelling
- Try first few letters only
- Uncheck "PDF only"

**Viewer not loading**
- Make sure terminal is still open
- Run `sf view` again

**Can't find a document**
- Try searching by customer name
- Document might be attached to a different record

## Quick Reference

| Task | Steps |
|------|-------|
| Find customer documents | Explorer → Account Name → type name |
| Find deal documents | Explorer → Opportunity Name → type name |
| Find invoice | Object dropdown → Invoice → search number |
| Preview PDF | Click document in results |

**You don't need technical skills — just type and click!**
