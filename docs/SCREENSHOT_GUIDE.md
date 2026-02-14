---
orphan: true
---

# Screenshot Guide for Documentation

This guide lists all screenshots needed for the documentation. Please capture these screenshots while the viewer is running and save them to `docs/_static/images/viewer/`.

## Prerequisites

1. Launch the viewer:
   ```bash
   sfdump db-viewer -d exports/export-2026-01-26
   ```

2. Open browser to http://localhost:8501

3. Prepare for screenshots:
   - Use a clean browser window (close extra tabs for clarity)
   - Use default zoom level (100%)
   - Capture full browser window OR just the viewer interface (your choice)

## Screenshot List

### Section 1: Getting Started

**01-launch.png** - Terminal showing viewer starting
- Show the terminal/command prompt
- Include the command: `sfdump db-viewer -d ...`
- Show the output with URLs (http://localhost:8501)
- Crop to show just the relevant terminal output

**02-explorer-landing.png** - Explorer view (default landing page)
- Open the viewer in browser
- Show the full-width Explorer with search box, no sidebar visible
- Show the "DB Viewer" button in the top-right corner
- This is the "overview" shot showing the landing page

**03-db-viewer-interface.png** - DB Viewer with record selected
- Click "DB Viewer" button to switch to DB Viewer mode
- Select any Account (e.g., search for "Acme Corp")
- Show all panels: Sidebar (with "Back to Explorer" button), Record List, Details
- This shows the full DB Viewer layout

**04-select-object.png** - Object dropdown in DB Viewer sidebar
- Click the Object dropdown in sidebar
- Capture the dropdown menu expanded
- Show various objects available (Account, Opportunity, Invoice, etc.)

### Section 2: Browsing Records (DB Viewer)

**05-search-records.png** - Searching for records
- In sidebar search box, type "Acme Corp"
- Show the filtered results in the left column
- Highlight that results update as you type

**06-record-details.png** - Account record details tab
- Select an Acme Corp account
- Show the Details tab selected
- Display showing account fields (Name, Type, etc.)

### Section 3: Navigating Relationships (DB Viewer)

**07-children-tab.png** - Children tab with relationships
- Still viewing an Acme Corp Account
- Click the Children tab
- Expand one relationship (e.g., Opportunity)
- Show the relationship name and count

**08-navigate-down.png** - Selecting and opening a child
- In expanded Opportunity relationship
- Show the dropdown with child records
- Show the "Open" button
- Optional: Include breadcrumbs in sidebar

**09-contextual-message.png** - Closed Lost opportunity message
- Navigate to Opportunity: Acme Corp_BE-NPI-SC_Q2_2020
- Click Children tab
- Expand c2g__codaInvoice__c relationship
- **Capture the contextual message**:
  ```
  **Note:** No invoices found. This is expected for Closed Lost opportunities
  (Stage: Closed Lost), as they typically don't generate invoices.
  ```

### Section 4: Explorer (Document Search)

**10-explorer-search.png** - Explorer search interface
- Switch back to Explorer (click "Back to Explorer" in sidebar)
- Show the search interface BEFORE entering search
- Highlight: Search box and filter options
- Full-width layout, no sidebar

**11-search-account.png** - Search by Account (Acme Corp)
- Click Additional Filters, type "Acme Corp" in Account Name field
- Show match count
- Show results table with account_name and opp_name columns visible
- Make sure columns are wide enough to read

**12-search-opportunity.png** - Search by Opportunity (Beta Industries)
- Clear Account search
- Type "Beta Industries" in Opportunity Name field
- Show match count
- Results table visible

**13-pdf-preview.png** - PDF preview showing document
- Search for "RFP Response Acme"
- Select the document from dropdown
- Scroll down to show the PDF preview
- Capture the PDF rendering inline (at least first page visible)

**14-open-parent.png** - Open parent record button
- With a document selected
- Highlight the "Open parent record" button
- Show that clicking it switches to DB Viewer with the record

### Section 5: Finding Documents (Simplified Guide)

**user-01-home.png** - Viewer home page (Explorer landing)
- Fresh viewer page showing Explorer
- Full-width search, no sidebar
- Clean, uncluttered shot for beginners

**user-02-search-box.png** - Search box location
- Highlight/circle the search box
- Make it obvious for naive users where to type

**user-03-account-search.png** - Account Name search box
- Close-up of the "Additional Filters" expanded
- Show the "Account Name" input field
- Maybe show cursor in the field or partially typed name

**user-04-search-results.png** - Search results after typing Acme Corp
- Results showing for Acme Corp
- Clear view of the match counter
- Results table visible with account_name column

**user-05-pdf-preview.png** - PDF preview (user-friendly angle)
- Similar to #13 but emphasize the ease of use
- Show full document preview
- Maybe zoom in on the PDF content

**user-06-opp-search.png** - Opportunity Name search box
- Similar to user-03 but for Opportunity field
- Show where to type opportunity name

**user-07-invoice-search.png** - Finding specific invoice by search
- Explorer view with invoice number typed in search box
- Show matching result in the table
- Highlight the simplicity: just type and find

**user-08-contract-search.png** - Finding contracts by keywords
- Explorer search results
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
            ├── 02-explorer-landing.png
            ├── 03-db-viewer-interface.png
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

- [ ] All screenshots captured
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
2. 11-search-account.png (Account search)
3. 12-search-opportunity.png (Opportunity search)
4. 13-pdf-preview.png (PDF preview working)

**Important (for complete documentation):**
5. 02-explorer-landing.png (Explorer landing page)
6. 03-db-viewer-interface.png (DB Viewer layout)
7. 07-children-tab.png (Relationships)
8. 09-contextual-message.png (Shows contextual feature)

**Nice to have:**
9. All remaining screenshots for completeness

Thank you for helping complete the documentation!
