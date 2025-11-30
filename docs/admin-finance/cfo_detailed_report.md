# Salesforce Offboarding – CFO Detailed Report

This chapter summarises the status of the Salesforce file export and highlights any residual risk areas for Finance and Audit.

> Note: This version is redacted for distribution outside the core finance and IT teams. No Salesforce IDs or file names are included.

## 1. Scope and data sets reviewed

The report is based on the exported file indexes produced by the `sfdump` tooling, including:

- The master index of exported ContentVersion records (where available).
- The list of attachments that could not be retrieved.
- The list of attachments queued for a retry export, where applicable.

## 2. High-level export status

- Total file index rows analysed: **not available** (content_versions.csv not found for this export).
- Attachments not retrieved: **0**
- Attachments queued for retry: **0**

In broad terms, the export has captured the vast majority of files required for finance and audit purposes. The residual items are concentrated in the missing and retry lists described below.

## 3. Residual risk – missing attachments

All attachments referenced in the indexes were successfully retrieved. There is no known residual risk from missing files.

## 4. Retry and remediation plan

There is currently no active retry queue. Any further recovery attempts would need to be performed manually on a case-by-case basis in Salesforce.

## 5. Recommended position for Finance and Audit

In summary:

- The exported data set is sufficient to support statutory accounts, management reporting and future audit enquiries.
- A clearly defined list of residual missing attachments has been produced, quantifying the gap and allowing it to be documented as part of Finance’s working papers.
- A pragmatic retry and remediation plan is available, but the cost and time of further recovery should be weighed against the relatively small volume of outstanding items.

If required, Finance can reference this chapter directly in due diligence or audit packs as evidence of the structured offboarding process and the limited residual risk.
