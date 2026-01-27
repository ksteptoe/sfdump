# Audit Completeness

How to demonstrate that Salesforce data has been fully extracted.

## Required Evidence

- content_versions.csv
- attachments.csv
- *_files_index.csv for finance objects
- Missing-file report

## Verifying Finance Objects

Check:

- c2g__codaInvoice__c
- c2g__codaPurchaseInvoice__c
- ffvat__VatReturn__c
- ffps_po__PurchaseOrder__c

## Auditor Checklist

- Are all ContentVersions present?
- Are all attachments present?
- Have retries succeeded?
- Are parent objects consistent?
