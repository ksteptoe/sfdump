# GUI TODO (sfdump viewer)

> Objective: make it fast and reliable to find **all documents** (especially PDFs) by navigating from:
> - Accounts → Opportunities → related finance objects
> - Finance objects (Invoices / Transactions / Journals) → back to Opportunities / Accounts

---

## Done

- NAV-001 Breadcrumb jump should not duplicate stack (commit: 0441558)
- DB-001 URGENT  Not All files retreived from db and sfdump does not know of them
- DOC-001 Preview doc selector must actually preview (and not “do nothing”)
- NAV-002 Back button (main pane) pops the object

---

## Working rules

- **One change per PR/commit** (small, reviewable, low-regression).
- Every item below has:
  - **DoD** (definition of done)
  - **Smoke test** steps (what we click to confirm)
- Use **pusht** to add new ideas into *Next* or *Later*.
- Use **popt** to pull exactly one item into focus (top of *Now*).

---

## How to use this with ChatGPT

When messaging, copy/paste:

- `popt: <ITEM-ID> <title>`
- the **DoD**
- the **smallest relevant code block**
- (after changes) smoke test results + `git status -sb`

---

## Smoke test checklist (run after every change)

1. Search Account in left pane
2. Select Opportunity in right pane (child list)
3. Push into the child record (navigate in)
4. Documents tab:
   - Select doc → preview shows
   - Open doc → OS opens the file
   - Download works
5. Navigation:
   - Back returns to previous record
   - Breadcrumb click jumps (does not duplicate stack)

---

## Now (popt queue)

**Active popt:** DOC-002
### DOC-002 Documents panel: standardised renderer
**Goal:** One shared UI component that lists docs, previews, and opens/downloads.
**Approach:** Introduce `ui/documents_panel.py` with `render_documents_panel(...)`.

**DoD**
- Documents tab uses shared panel
- No duplicated preview logic scattered across UI files

---
### DOC-003 Document Explorer (global search)
**Goal:** Search across *all* documents via `meta/master_documents_index.csv`.
**Features**
- Search box (filename/keyword)
- Filters: source/object type/content type (PDF first)
- Preview/open/download from results

**DoD**
- Can find a known contract PDF by search term within seconds
- Selecting a result can preview + navigate to parent record (if indexed)

---

### REL-001 Show “documents in subtree”
**Goal:** From Account/Opportunity, show documents for the whole subtree (Opportunity + children).
**Approach:** Use traversal to collect descendant IDs → filter global index.

**DoD**
- Starting at an Opportunity, you can view all attached docs in its descendant tree

---

## Next (pusht candidates)





### REL-002 “Inbound references” view (graph-ish navigation)
**Goal:** From finance objects (invoice/journal/transaction), discover links back to Opportunity/Account even if schema is incomplete.
**Approach**
- Scan tables for columns ending in `Id`
- Find rows where FK equals current record id
- Display “objects referencing this record” list with navigation links

**DoD**
- From an invoice/journal record, you can hop to at least one upstream commercial object (Opportunity/Account) when the data supports it

---

## Later (parked / research)

- Improve preview performance for large PDFs
- Better PDF embedding fallback behaviour (browser-dependent)
- Add “Copy file path” / “Copy record id”
- Add “Open folder” for local file location
- Add recency/size sorting for document lists

---

## Notes / context

- Existing indices:
  - `record_documents`: fast per-record listing
  - `meta/master_documents_index.csv`: global search index
- Primary target docs:
  - Contracts (PDF) attached to Opportunities
  - Invoices / credit notes / cash entries linked via transactions/journals
  - Anything connecting finance objects ↔ opportunities/accounts
