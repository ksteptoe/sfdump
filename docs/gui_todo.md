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
- DOC-002 Documents panel: standardised renderer
- DOC-003 Document Explorer (global search)
- REL-001 Show “documents in subtree”

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

## Now (popt queue)  REL-002 Tables for Opp -> invoice -> Journal relationships

**Active popt:** REL-002 Understand and build tables that describe the (forward) realtionships between Opportunities and invoices
### REL-002 Understand and build tables that describe the (forward) realtionships between Opportunities and invoices
**Goal:** Understand and Build (create if neccessary) relationsips between Opportunities and Financial records e.g.
**Approach**
- Understand the Schema properly. Build and analyse SF queries to understand these relationships and in addition I will give a picture of the schema in SF and we need to build this.
- Where there are one to many relationships between e.g. Invoices and Opportunities then we need to create the reverse TABLE

**DoD**
- Using SQlite quiries on the db we show that the tables have been built ready for the next stage. So that a later popt From an opinvoice/journal record, you can hop to at least one upstream commercial object (Opportunity/Account) when the data supports it
can build the GUI to navigate down to these objects

---

## Next (pusht candidates)

### REL-003 “Inbound references” view (graph-ish navigation)
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
