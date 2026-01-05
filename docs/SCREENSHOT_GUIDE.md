---
orphan: true
---

# Screenshot Guide for Documentation

This guide lists all screenshots needed for the documentation. Please capture these screenshots while the viewer is running and save them to `docs/_static/images/viewer/`.

## Prerequisites

1. Launch the viewer:
   ```bash
   sfdump db-viewer --db exports/export-2025-12-31/meta/sfdata.db
   ```

2. Open browser to http://localhost:8503

3. Prepare for screenshots:
   - Use a clean browser window (close extra tabs for clarity)
   - Use default zoom level (100%)
   - Capture full browser window OR just the viewer interface (your choice)

## Screenshot List

### Section 1: Getting Started

**01-launch.png** - Terminal showing viewer starting
- Show the terminal/command prompt
- Include the command: `sfdump db-viewer --db ...`
- Show the output with URLs (http://localhost:8503)
- Crop to show just the relevant terminal output

**02-interface.png** - Main viewer interface
- Open the viewer in browser
- Select any Account (e.g., search for "VITEC")
- Show all three panels: Sidebar, Record List, Details
- This is the "overview" shot showing the whole interface

**03-select-object.png** - Object dropdown
- Click the Object dropdown in sidebar
- Capture the dropdown menu expanded
- Show various objects available (Account, Opportunity, Invoice, etc.)

### Section 2: Browsing Records

**04-search-records.png** - Searching for records
- In sidebar search box, type "VITEC"
- Show the filtered results in the middle panel
- Highlight that results update as you type

**05-record-details.png** - Account record details tab
- Select a VITEC account
- Show the Details tab selected
- Display showing account fields (Name, Type, etc.)

### Section 3: Navigating Relationships

**06-children-tab.png** - Children tab with relationships
- Still viewing a VITEC Account
- Click the Children tab
- Expand one relationship (e.g., Opportunity)
- Show the relationship name and count

**07-navigate-down.png** - Selecting and opening a child
- In expanded Opportunity relationship
- Show the dropdown with child records
- Show the "Open" button
- Optional: Include breadcrumbs at top

**08-contextual-message.png** - Closed Lost opportunity message
- Navigate to Opportunity: VITEC_BE-NPI-SC_Q2_2020
- Click Children tab
- Expand c2g__codaInvoice__c relationship
- **Capture the contextual message**:
  ```
  ℹ️ No invoices found. This is expected for Closed Lost opportunities
  (Stage: Closed Lost), as they typically don't generate invoices.
  ```

### Section 4: Document Explorer

**09-document-explorer.png** - Document Explorer main interface
- Click Document Explorer tab
- Show the search interface BEFORE entering search
- Highlight: "Search by Account or Opportunity" section
- Show all the filter options

**10-search-account.png** - Search by Account (VITEC)
- Type "VITEC" in Account Name field
- Show "Matches: 65" (or whatever number shows)
- Show results table with account_name and opp_name columns visible
- Make sure columns are wide enough to read

**11-search-opportunity.png** - Search by Opportunity (Degirum)
- Clear Account search
- Type "Degirum" in Opportunity Name field
- Show "Matches: 75" (or whatever number)
- Results table visible

**12-pdf-preview.png** - PDF preview showing document
- Search for "RFP Response Vitec"
- Select the document from dropdown
- Scroll down to show the PDF preview
- Capture the PDF rendering inline (at least first page visible)

**13-open-parent.png** - Open parent record button
- With a document selected
- Highlight the "Open parent record" button
- Optional: Show the parent info (Opportunity name) next to it

### Section 5: Finding Documents (Simplified Guide)

**user-01-home.png** - Viewer home page (simple view)
- Fresh viewer page
- No object selected or just default view
- Clean, uncluttered shot for beginners

**user-02-doc-explorer-tab.png** - Document Explorer tab location
- Highlight/circle where the "Document Explorer" tab is
- Make it obvious for naive users where to click

**user-03-account-search.png** - Account Name search box
- Close-up of the "Account Name" input field
- Maybe show cursor in the field or partially typed name
- Make it clear this is where to type

**user-04-search-results.png** - Search results after typing VITEC
- Results showing for VITEC
- Clear view of the "Matches: 73" counter
- Results table visible with account_name column

**user-05-pdf-preview.png** - PDF preview (user-friendly angle)
- Similar to #12 but emphasize the ease of use
- Show full document preview
- Maybe zoom in on the PDF content

**user-06-opp-search.png** - Opportunity Name search box
- Similar to user-03 but for Opportunity field
- Show where to type opportunity name

**user-07-invoice-search.png** - Finding specific invoice
- Sidebar showing Invoice object selected
- Search box with invoice number typed
- Invoice selected in list

**user-08-contract-search.png** - Finding contracts by keywords
- Document Explorer search results
- Results filtered to show PDFs
- Filenames showing "contract", "RFP", "Agreement" keywords
- Highlight a contract file in the results

## Screenshot Tips

### For Best Quality

1. **Resolution**: 1920x1080 or higher recommended
2. **Format**: PNG (better quality than JPG for UI screenshots)
3. **Naming**: Use exact filenames listed above
4. **Cropping**:
   - Crop out browser chrome (address bar, bookmarks) if distracting
   - OR keep browser chrome for context (up to you)
   - Keep screenshots consistent (all with chrome OR all without)

### For Clarity

1. **Zoom**: Use 100% browser zoom for crisp text
2. **Window size**: Make browser window large enough to show content clearly
3. **Highlighting**: You can add arrows/circles/highlights AFTER taking screenshots (optional)
4. **Mouse cursor**: Hide cursor for cleaner shots (or show it pointing at important elements)

### Screenshot Tools

**Windows:**
- Windows + Shift + S (Snipping Tool)
- Save to `docs\_static\images\viewer\`

**Mac:**
- Cmd + Shift + 4 (select area)
- Cmd + Shift + 3 (full screen)
- Save to `docs/_static/images/viewer/`

**Linux:**
- Screenshot app (varies by distro)
- gnome-screenshot, flameshot, etc.

## Saving Screenshots

Save all screenshots to:
```
docs/_static/images/viewer/
```

Directory structure:
```
docs/
└── _static/
    └── images/
        └── viewer/
            ├── 01-launch.png
            ├── 02-interface.png
            ├── 03-select-object.png
            ...
            └── user-08-contract-search.png
```

## After Capturing Screenshots

1. Review each screenshot for clarity
2. Ensure no sensitive data is visible (customer names are OK, but no SSNs, credit cards, etc.)
3. Verify filenames match exactly (case-sensitive on some systems)
4. Optional: Use image editing to add arrows/highlights to important areas
5. Rebuild docs to see them in context:
   ```bash
   cd docs
   make html
   open _build/html/index.html
   ```

## Quick Checklist

- [ ] All 21 screenshots captured
- [ ] Saved to correct directory with exact filenames
- [ ] No sensitive data visible
- [ ] Clear, readable text in all screenshots
- [ ] Consistent browser chrome (all with OR all without)
- [ ] Screenshots show the correct content per description above

## Questions?

If any screenshot is unclear or you need guidance on what exactly to capture, the documentation includes descriptions of what each screenshot should show. You can also:

1. Look at the context where the image is referenced in the .md files
2. Read the surrounding text to understand what the screenshot illustrates
3. Prioritize screenshots for finding_documents.md first (most important for users)

## Priority Order

If you're short on time, capture screenshots in this order:

**Critical (for naive users):**
1. user-01 through user-08 (Finding Documents guide)
2. 10-search-account.png (Account search)
3. 11-search-opportunity.png (Opportunity search)
4. 12-pdf-preview.png (PDF preview working)

**Important (for complete documentation):**
5. 02-interface.png (Overview)
6. 06-children-tab.png (Relationships)
7. 08-contextual-message.png (Shows our new feature!)
8. 09-document-explorer.png (Document Explorer interface)

**Nice to have:**
9. All remaining screenshots for completeness

Thank you for helping complete the documentation!
