# Interpreting Reports

This explains how to read a generated report.

## Executive Summary

Shows:

- total attachments
- total content versions
- missing counts
- recovered files
- unrecovered files

## Diagnostic Evidence

Contains:
- attachment ID or anonymised label
- parent ID or anonymised label
- retry status
- error message

## Impact on Parent Records

Breakdown by:

- Opportunity
- Account
- Finance objects
- HR objects
- PSA objects

Shows how many missing files were attached to each.

## Redacted vs Full

- Redacted uses ATTACHMENT_n and PARENT_n
- Full uses real Salesforce IDs

Use redacted for docs, full for internal distribution.
