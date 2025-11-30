# CFO Detailed Offboarding Report (Template)

> **Purpose**
> This chapter template is designed to be populated by the `sfdump cfo-report` command and included in the finance due‑diligence pack. It is written in plain Markdown so it can be:
> - Viewed directly as a standalone report; or
> - Included into the Sphinx documentation tree for PDF/HTML generation.

---

## 1. Executive Summary

- **Scope of extraction:** `<<describe which Salesforce org, date range, and business areas were included>>`
- **Time window analysed:** `<<e.g. 2014‑01‑01 to 2025‑01‑31>>`
- **Total file records discovered:** `<<N_total>>`
- **Files successfully extracted:** `<<N_ok>> (<<P_ok>>%)`
- **Files still missing / inaccessible:** `<<N_missing>> (<<P_missing>>%)`
- **Residual risk level:** `<<Low / Medium / High>>`

---

## 2. Data Sources and Method

### 2.1 Objects and relationships

- **Attachment** and **ContentVersion** objects were scanned in the source Salesforce org.
- Each file was linked back to its **parent record** via the appropriate relationship fields (e.g. invoice, quote, contract, opportunity).
- A canonical index CSV (`content_versions.csv`) was created to track:
  - File Id and type
  - Parent SObject and Id
  - Parent business key (e.g. InvoiceNumber, Contract reference, Quote number)
  - Export status and any error codes

### 2.2 Extraction runs

For this exercise:

- **Export root:** `<<path or logical name of export batch>>`
- **Initial extraction run:** `<<timestamp>>`
- **Retry / remediation runs:** `<<timestamps and high‑level notes>>`

The `sfdump` tooling recorded a row for every file encountered, regardless of whether the binary could be downloaded, so that residual risk can be quantified.

---

## 3. Coverage Statistics

### 3.1 Overall coverage

- **Total file records in scope:** `<<N_total>>`
- **Successfully exported files:** `<<N_ok>> (<<P_ok>>%)`
- **Missing / failed files:** `<<N_missing>> (<<P_missing>>%)`

Breakdown by **file container type**:

- **Classic Attachments:** `<<N_att_ok>> / <<N_att_total>> (<<P_att_ok>>% ok)`
- **ContentVersion / Files:** `<<N_cv_ok>> / <<N_cv_total>> (<<P_cv_ok>>% ok)`

### 3.2 Coverage by business object

| Parent object           | In scope | Files found | Files exported | Missing/failed | Notes                          |
|-------------------------|---------:|------------:|---------------:|---------------:|--------------------------------|
| Invoice                 |         |            |                |                |                                |
| SalesforceInvoice       |         |            |                |                |                                |
| SalesforceContract      |         |            |                |                |                                |
| SalesforceQuote         |         |            |                |                |                                |
| Other financial objects |         |            |                |                |                                |

*(This table is intended to be populated from the canonical index CSV.)*

---

## 4. Missing / Failed Files

### 4.1 Summary

- **Total missing / failed:** `<<N_missing>>`
- **Unique parent records affected:** `<<N_parents_missing>>`
- **Proportion of parents with at least one missing file:** `<<P_parents_missing>>%`

### 4.2 Common failure reasons

Typical reasons observed (to be confirmed per run):

- Permission / access‑control failures (HTTP 403)
- Records in the index with no longer existing binary (`BODY DELETED` or similar)
- Files exceeding organisational limits or blocked by governance rules
- Intermittent connectivity / timeout issues not resolved by automatic retry

### 4.3 Materiality assessment

For each failure category, the finance team should assess:

- **Does the missing file affect revenue recognition evidence?**
- **Does it affect contract / obligation evidence?**
- **Is the information reconstructible from other systems (e.g. ERP, banking, document repositories)?**

Where possible, a short narrative should be added here if any gaps are considered **material** to financial statement support.

---

## 5. Remediation Attempts and Residual Risk

### 5.1 Automated retries

- **Retry batch executed:** `<<timestamp(s)>>`
- **Files successfully recovered during retry:** `<<N_recovered>>`
- **Files still missing after retry:** `<<N_still_missing>>`

### 5.2 Alternative evidence paths

For each class of missing file, indicate:

- Whether equivalent information exists in:
  - ERP or accounting system
  - Bank statements and reconciliations
  - Separate document management systems (e.g. SharePoint, shared drive)
- Whether the finance or legal teams are comfortable relying on that alternative evidence.

### 5.3 Residual risk statement

Provide a concise conclusion for the diligence pack, for example:

> “Based on the extraction statistics and follow‑up remediation, management considers the residual risk of missing supporting documentation for revenue, debtor, and contract‑related balances to be **low / medium / high**. The missing items relate primarily to `<<describe>>` and do **not / may** impact the ability to evidence key balances.”

---

## 6. Appendices

### Appendix A – Extraction Run Metadata

- Export batch identifier(s)
- Salesforce org identifier(s)
- API versions used
- Date/time window of each run
- Tool versions (`sfdump` version, Python version)

### Appendix B – File Index References

Location of CSV/Excel indexes that support this report (these files remain **internal** and are **not** required to be shared with external parties unless specifically requested):

- `content_versions.csv`
- `attachments_missing.csv`
- `attachments_missing_retry.csv`
- Any Excel workbooks derived from these CSVs for pivoting / summarisation.

---

*End of CFO detailed offboarding report template.*
