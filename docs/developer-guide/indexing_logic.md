# Indexing Logic

`sfdump` builds indexes connecting each file to its parent business object.

## Why Index Files?

- Finance audit trails
- HR compliance
- Opportunity/Account reconstruction
- Facilitates redaction anonymisation

## Index Sources

- Attachment.ParentId relationships
- ContentDocument → ContentVersion → Linked records
- Custom parent objects (e.g. PSA, HR, FinanceForce)

## Label Fields

Some objects have special label fields:

```python
INDEX_LABEL_FIELDS = {
  "SalesforceInvoice": "InvoiceNumber",
  "SalesforceContract": "BillingCompany",
  "SalesforceQuote": "SalesforceContractId",
}
```

## Output Files

Generated under:

```
links/<Object>_files_index.csv
```

Each contains:

- Parent record ID
- Parent descriptive name
- File ID
- File name
- File path

## Use in Reports

Indexing feeds:

- redaction mapping
- parent impact reporting
- hierarchical summaries
