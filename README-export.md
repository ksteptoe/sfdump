# Salesforce / FinancialForce Export Guide (sfdump + Makefile.export)

This guide explains how to use `sfdump` together with `Makefile.export` to pull
a **repeatable, auditable export** of our Salesforce and FinancialForce data
for due diligence and off-platform backup.

It covers:

- Where exports go on disk
- How the date handling works (`EXPORT_DATE`)
- How to export files & attachments (with optional indexing)
- How to rebuild file indexes without re-downloading everything (`--index-only`)
- How to export CRM / HR / FinancialForce objects to CSV
- How to re-run old exports

---

## 1. Directory layout

By default, each export lives in a date-stamped directory:

```text
<BASE_EXPORT_ROOT>/
  export-YYYY-MM-DD/
    files/   # Files & Attachments downloaded by `sfdump files`
    csv/     # CSV exports for objects (Account, Opportunity, ff* etc.)
    meta/    # Metadata such as list of all sObjects
```

In the Makefile the key variables are:

```make
BASE_EXPORT_ROOT ?= C:/Users/kevin/OneDrive - Sondrel Ltd/SF
EXPORT_DATE      ?= $(shell date +%Y-%m-%d)
EXPORT_ROOT      ?= $(BASE_EXPORT_ROOT)/export-$(EXPORT_DATE)

CSV_DIR          := $(EXPORT_ROOT)/csv
FILES_DIR        := $(EXPORT_ROOT)/files
META_DIR         := $(EXPORT_ROOT)/meta
```

So, for example, with:

```text
BASE_EXPORT_ROOT = C:/Users/kevin/OneDrive - Sondrel Ltd/SF
EXPORT_DATE      = 2025-11-15
```

you get:

```text
EXPORT_ROOT = C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15
CSV_DIR     = C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/csv
FILES_DIR   = C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/files
META_DIR    = C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/meta
```

If needed, you can override `BASE_EXPORT_ROOT` per run:

```bash
make -f Makefile.export BASE_EXPORT_ROOT="D:/Backups/SF" export-all
```

---

## 2. Prerequisites

- Python virtualenv for the project is activated.
- `sfdump` is installed (editable or normal install) and on your PATH.
- Salesforce JWT / OAuth env vars are set (or `.env` + `python-dotenv`).

Quick sanity check:

```bash
sfdump objects --all | head
```

If that works, you’re good.

---

## 3. Using EXPORT_DATE (very important)

The Makefile sets `EXPORT_DATE` to **today** by default:

```make
EXPORT_DATE ?= $(shell date +%Y-%m-%d)
```

You can override it either:

### 3.1 Per command

```bash
make -f Makefile.export EXPORT_DATE=2025-11-15 export-all
```

### 3.2 For the whole shell session

```bash
export EXPORT_DATE=2025-11-15   # Git Bash / Linux / macOS
make -f Makefile.export export-all
make -f Makefile.export export-crm-all
make -f Makefile.export export-ffa
make -f Makefile.export export-hr
```

**Tip:** To see what make thinks the paths are, run:

```bash
make -f Makefile.export export-show-config
```

This prints `EXPORT_DATE`, `EXPORT_ROOT`, `CSV_DIR`, `FILES_DIR`, and `META_DIR`.

---

## 4. Main Make targets

Common targets (run with `make -f Makefile.export <target>`):

- `help`
  Show a short help summary.

- `export-all`
  End-to-end export for the current `EXPORT_DATE`:
  - Files & Attachments (plus indexes for key objects)
  - Core CRM objects
  - FinancialForce / ERP objects (ff…)
  - HR / employment objects
  - Object list (`meta/all_objects.txt`)

- `export-files`
  Download all `ContentVersion` + `Attachment` records into `FILES_DIR` and
  attempt to build helper indexes by key parent objects (e.g. `Opportunity`,
  `Account`, `SalesforceInvoice`, `fferpcore__BillingDocument__c`, etc.).

- `export-files-index-only`
  Rebuild only the file link indexes in `FILES_DIR` (no new downloads) using
  `sfdump files --index-only` and the configured `FILE_INDEX_OBJECTS`. Requires
  that you have already run `export-files` or `export-all` for the same
  `EXPORT_DATE`.

- `export-crm-all`
  Export core CRM objects and related activity objects to CSV.

- `export-ffa`
  Export FinancialForce / ERP objects (billing documents, PO, GRN, VAT, etc.).

- `export-hr`
  Export HR / employment / salary history objects to CSV.

- `export-meta`
  Export a complete sObject list to `meta/all_objects.txt`.

- `export-archive`
  Zip the entire `EXPORT_ROOT` directory into `EXPORT_ROOT.zip`.

---

## 5. Files & Attachments export and indexing

### 5.1 Files export

The `export-files` target runs something equivalent to:

```bash
sfdump files \
  --out "<FILES_DIR>" \
  --index-by Opportunity \
  --index-by Account \
  --index-by Project__c \
  --index-by Invoices__c \
  --index-by SalesforceInvoice \
  --index-by SalesforceContract \
  --index-by SalesforceQuote \
  --index-by fferpcore__BillingDocument__c \
  --index-by ffc_statex__StatementAccount__c \
  --index-by ffps_po__PurchaseOrder__c \
  --index-by ffps_po__GoodsReceiptNote__c \
  --index-by ffvat__VatReturn__c \
  --index-by Engineer__c \
  --index-by JobApplication__c \
  --index-by HR_Activity__c \
  --index-by Salary_History__c
```

Behaviour:

- **All files/attachments** are downloaded regardless of whether the indexing
  step succeeds.
- If an index build fails for a particular object (e.g. SOQL field mismatch),
  we log a warning but **do not abort** the export.

The index files themselves live under `FILES_DIR` and make it easier to see
“all files attached to a given Opportunity / Invoice / PO / JobApplication”.

### 5.2 Index-only mode (debug-friendly)

Once you have done **at least one full files export** for a given
`EXPORT_DATE`, you can rebuild the indexes **without** re-downloading any
files.

`sfdump files` supports an `--index-only` mode:

```bash
# Full run (downloads + indexes)
sfdump files \
  --out "./exports/export-2025-11-15/files" \
  --index-by Opportunity \
  --index-by SalesforceInvoice \
  ...

# Later: rebuild only the index CSVs for the same folder
sfdump files \
  --out "./exports/export-2025-11-15/files" \
  --index-by Opportunity \
  --index-by SalesforceInvoice \
  --index-only
```

The Makefile provides a convenience target:

```bash
make -f Makefile.export EXPORT_DATE=2025-11-15 export-files-index-only
```

This is ideal while iterating on the indexing logic (`build_files_index`,
`INDEX_LABEL_FIELDS`, etc.) because it skips the long attachment download.

**Important:**

- `--index-only` does **not** download any file bodies; it only queries IDs and
  relationships and rewrites the CSVs in `files/links/`.
- `--index-only` is mutually exclusive with `--estimate-only`.

---

## 6. CSV exports

Each CSV export is represented by a `.done` sentinel in `CSV_DIR`, e.g.:

```text
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/csv/
  Account.csv
  Account.done
  Opportunity.csv
  Opportunity.done
  ...
```

The Makefile pattern rule is:

```make
$(CSV_DIR)/%.done:
	@echo "=== Exporting $* to $(CSV_DIR) ==="
	@mkdir -p "$(EXPORT_ROOT)" "$(CSV_DIR)"
	@$(SFDUMP) csv --object $* --out "$(EXPORT_ROOT)" && touch "$@"
```

So for the target:

```text
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/csv/Account.done
```

the command is:

```bash
sfdump csv --object Account --out "C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15"
```

and `sfdump` writes the file:

```text
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/csv/Account.csv
```

---

## 7. Exporting a single object (csv-one)

To make it easy to export only one object, we have a helper target:

```make
.PHONY: csv-one
csv-one:
	@if [ -z "$(OBJ)" ]; then \
	  echo "Usage: make -f Makefile.export csv-one OBJ=Account"; \
	  exit 1; \
	fi
	$(MAKE) -f Makefile.export $(CSV_DIR)/$(OBJ).done
```

Usage examples:

```bash
# Export just Account
make -f Makefile.export EXPORT_DATE=2025-11-15 csv-one OBJ=Account

# Export just SalesforceInvoice
make -f Makefile.export EXPORT_DATE=2025-11-15 csv-one OBJ=SalesforceInvoice
```

---

## 8. Re-running / inspecting older exports

Because exports are date-stamped, you can have multiple snapshots, e.g.:

```text
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-15/
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-16/
C:/Users/kevin/OneDrive - Sondrel Ltd/SF/export-2025-11-30/
```

To re-run or add objects for a particular day (say `2025-11-15`), always pass
the same `EXPORT_DATE`:

```bash
# Add a missing object to an existing export
make -f Makefile.export EXPORT_DATE=2025-11-15 csv-one OBJ=Something__c

# Re-run CRM export into the same day's folder
make -f Makefile.export EXPORT_DATE=2025-11-15 export-crm-all
```

---

## 9. Special handling: SalesforceInvoice indexing

The file-indexing feature usually runs SOQL like:

```sql
SELECT Id, Name FROM <ParentObject>
```

For most objects (e.g. `Opportunity`, `Account`) this works.

However, `SalesforceInvoice` does **not** have a `Name` field, which causes:

```text
No such column 'Name' on entity 'SalesforceInvoice'.
```

To fix this, we special-case `SalesforceInvoice` in the indexing code to use
`InvoiceNumber` instead, via a mapping:

```python
INDEX_LABEL_FIELDS: dict[str, str] = {
    "SalesforceInvoice": "InvoiceNumber",
    # e.g. you can add more special cases later:
    # "ffps_po__PurchaseOrder__c": "Name__c",
}
```

This results in SOQL of the form:

```sql
SELECT Id, InvoiceNumber FROM SalesforceInvoice
```

and ensures the `record_name` column in the file index CSVs contains a useful
identifier, without breaking other objects that still use `Name`.

See the `build_files_index` implementation in `sfdump.command_files` for details.

---

## 10. Common issues / troubleshooting

- **“Failed to describe object ''”**
  Usually means `sfdump csv` was called with an empty `--object` argument.
  The current Makefile uses `$*` in the pattern rule to ensure this doesn’t happen.

- **“No such column 'Name' on entity 'SalesforceInvoice'”**
  Expected if the indexer still assumes every object has `Name`. Fix is to use
  `InvoiceNumber` for `SalesforceInvoice` as described above (and keep
  `INDEX_LABEL_FIELDS` up to date).

- **Accidentally wrong date**
  If you forget to set `EXPORT_DATE`, the Makefile uses “today”.
  Use `export-show-config` to see what it’s doing, and set `EXPORT_DATE`
  explicitly if you want to target an older export folder.
