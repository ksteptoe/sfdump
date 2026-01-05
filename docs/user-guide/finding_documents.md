# Finding Documents - Quick Guide

**For:** Finance team members, accountants, contract managers
**Goal:** Find invoices, contracts, and financial documents quickly

This guide assumes you have **zero technical background**. If you can use a web browser, you can find documents in the archive.

## Before You Start

Someone in your IT team should have:
1. Exported all Salesforce data
2. Built a searchable database
3. Given you access to the viewer

**All you need is a web browser.**

## Opening the Viewer

### If the Viewer is Already Running

1. Open your web browser (Chrome, Firefox, Edge)
2. Go to: **http://localhost:8503**
3. You should see the document viewer interface

<!-- Screenshot: Viewer home page (user-01-home.png) -->

### If You Need to Start the Viewer

Ask your IT administrator to run this command for you, or follow these steps:

1. Open Terminal (Mac) or Command Prompt (Windows)
2. Type this command:
   ```
   sfdump db-viewer --db exports/export-2025-12-31/meta/sfdata.db
   ```
3. Press Enter
4. Look for "Local URL: http://localhost:8503"
5. Open that link in your browser

**Tip:** Keep the terminal window open - closing it stops the viewer.

## Finding Documents by Customer Name

This is the **most common task** - finding all documents for a specific customer account.

### Step-by-Step

1. **Click the "Document Explorer" tab** at the top

<!-- Screenshot: Document Explorer tab location (user-02-doc-explorer-tab.png) -->

2. **Type the customer name** in the "Account Name" box

   Example customer names:
   - VITEC
   - Example Corp
   - Continental
   - Freescale

<!-- Screenshot: Account Name search box (user-03-account-search.png) -->

3. **Results appear automatically** as you type

   Example: Typing "VITEC" shows **73 documents**

<!-- Screenshot: Search results showing 73 VITEC documents (user-04-search-results.png) -->

4. **Review the results table**

   The table shows:
   - **file_name**: Document name (e.g., "Invoice_2024.pdf")
   - **account_name**: Customer name (confirms it's the right account)
   - **opp_name**: Deal/opportunity name (if linked to a specific deal)
   - **object_type**: What kind of record (Invoice, Opportunity, etc.)

### What You Can Do Next

**Option A: Preview a PDF**
1. Select a document from the dropdown below the results
2. Scroll down to see the PDF preview
3. No download needed!

<!-- Screenshot: PDF preview showing document inline (user-05-pdf-preview.png) -->

**Option B: Note the file path**
1. Look at the `local_path` column
2. This tells you where the file is saved
3. Example: `files/06/0694J000...RFP_Response.pdf`
4. You can access this file directly from the export folder

**Option C: Filter results**
- Check "PDF first (only .pdf)" to see only PDF files
- Uncheck it to see all file types (Word, Excel, etc.)

## Finding Documents by Deal/Project Name

If you know the **opportunity** or **project name**, use this method.

### Step-by-Step

1. **Click "Document Explorer" tab**

2. **Type the project name** in the "Opportunity Name" box

   Example opportunity names:
   - Degirum_ORCA1.1_NPI_SOW_Q2_22
   - VITEC_BE-NPI-SC_Q2_2020
   - ETV Spitfire2

<!-- Screenshot: Opportunity Name search box (user-06-opp-search.png) -->

3. **Results show all documents for that deal**

   Example: "Degirum" shows **75 documents**

### Combined Search

You can search by **both** customer and deal:

**Example:** Find all VITEC documents from Q2 2020
1. Account Name: **VITEC**
2. Opportunity Name: **Q2_2020**
3. Results narrow to specific deal

This is very useful for finding contracts for specific projects.

## Finding a Specific Invoice

### Method 1: Search by Invoice Number

1. In the sidebar (left side), click the **Object** dropdown
2. Select **"Invoice"** (look for "c2g__codaInvoice__c")
3. In the search box, type the invoice number
   - Example: **SIN002795**
4. Select the invoice from the list
5. View details in the right panel

<!-- Screenshot: Searching for specific invoice (user-07-invoice-search.png) -->

### Method 2: Through Customer Account

1. Search for the customer in Document Explorer
2. Filter results to show only Invoice object type
3. Look through the list for your invoice number

### What Invoice Details Show

- Invoice number and date
- Customer name
- Total amount
- Status (Paid, Unpaid, etc.)
- Line items (in the Children tab)
- Attached PDF (in Documents tab)

## Finding a Specific Contract

Contracts are typically attached to Opportunities or Accounts.

### Step-by-Step

1. **Document Explorer tab**
2. **Account Name**: Type the customer name
3. **Check "PDF first"** - contracts are usually PDFs
4. **Look for filenames** with keywords:
   - "Contract"
   - "Agreement"
   - "RFP" (Request for Proposal)
   - "SOW" (Statement of Work)
   - "MSA" (Master Service Agreement)

<!-- Screenshot: Finding contracts by filename keywords (user-08-contract-search.png) -->

5. **Preview the PDF** to confirm it's the right contract

## Common Searches for Finance Teams

### All Invoices for a Customer

**Use Case:** Year-end reconciliation, audit

**Steps:**
1. Document Explorer
2. Account Name: [Customer]
3. Object types: Select "c2g__codaInvoice__c"
4. Results: All invoices for that customer

### Unpaid Invoices

**Use Case:** Collections, accounts receivable

**Steps:**
1. Sidebar: Select "Invoice" object
2. Search: (leave empty to see all)
3. In the list, look at the Status column
4. Manually filter for "Unpaid" or similar status

**Note:** For complex filtering, ask your IT admin about exporting to Excel.

### All Documents for Closed Deals

**Use Case:** Archive verification

**Steps:**
1. Document Explorer
2. Opportunity Name: [Deal name]
3. Results show all documents for that deal
4. Useful for project closeout

### Purchase Invoices/Bills

**Use Case:** Accounts payable, expense tracking

**Steps:**
1. Sidebar: Select "Purchase Invoice" object (c2g__codaPurchaseInvoice__c)
2. Search by vendor name or invoice number
3. View details and attached documents

## Understanding What You See

### Account vs Opportunity

**Account** = Customer company
- Example: "VITEC SA"
- Long-term relationship
- May have many deals/projects

**Opportunity** = Specific deal/project
- Example: "VITEC_BE-NPI-SC_Q2_2020"
- One-time sale or project
- Belongs to an Account

**Invoices** = Billing documents
- Usually linked to an Opportunity
- Show what was sold and for how much

### Why Some Records Have No Documents

You might see messages like:
```
ℹ️ No invoices found. This is expected for Closed Lost opportunities
(Stage: Closed Lost), as they typically don't generate invoices.
```

**This is normal!** The system explains why data might be missing:
- **Closed Lost** = Deal didn't happen, so no invoice
- **Closed Won** but no invoice = Invoice might be in a different system
- **New opportunity** = Deal in progress, invoice not created yet

Don't worry - this doesn't mean data is lost, just that it was never created.

## Tips & Tricks

### Partial Name Matching

You don't need to type the full name:
- Searching "VIT" finds "VITEC SA", "VITEC France", etc.
- Searching "Deg" finds "Degirum" opportunities

### Case Doesn't Matter

- "vitec" = "VITEC" = "Vitec"
- Search is case-insensitive

### PDF Preview Not Working?

If you see "Inline PDF preview requires PyMuPDF":
- Ask your IT admin to install it
- Meanwhile, you can still see the file path and access files directly

### Too Many Results?

Use filters to narrow down:
- Check "PDF first" to see only PDFs
- Add more specific search terms
- Combine Account + Opportunity search

### Browser Zoom

If text is too small:
- **Windows:** Ctrl + Plus (+) to zoom in
- **Mac:** Command + Plus (+) to zoom in

## Getting Help

### Common Issues

**"No matches found"**
- Check spelling of customer/opportunity name
- Try partial name (first few letters)
- Uncheck "PDF first" to see all file types

**Viewer not loading**
- Make sure the terminal window is still open
- Check you're going to the right URL (http://localhost:8503)
- Ask IT to restart the viewer

**Can't find a document you know exists**
- Try searching by customer name instead of deal name
- Check different object types
- Document might be attached to a different record type

### When to Ask IT for Help

- Exporting data to Excel for complex analysis
- Downloading multiple documents at once
- Setting up shared network access
- Technical errors or crashes

## Quick Reference Card

**Find documents for customer:**
```
1. Document Explorer tab
2. Account Name: [Customer]
3. Results appear
```

**Find documents for deal:**
```
1. Document Explorer tab
2. Opportunity Name: [Deal]
3. Results appear
```

**Find specific invoice:**
```
1. Sidebar: Select "Invoice"
2. Search: [Invoice number]
3. Select invoice
```

**Preview PDF:**
```
1. Find document in search results
2. Select from dropdown
3. Scroll down to preview
```

**Navigate to source record:**
```
1. Select a document
2. Click "Open parent record"
3. See the opportunity/invoice it came from
```

## Summary

The document viewer makes it easy to:
- ✅ Find all documents for any customer instantly
- ✅ Search by deal/project name
- ✅ Preview PDFs without downloading
- ✅ Locate invoices and contracts
- ✅ Access archived data after Salesforce shutdown

**You don't need technical skills - just type and click!**

For more advanced features, see the [Database Viewer Guide](database_viewer.md).
