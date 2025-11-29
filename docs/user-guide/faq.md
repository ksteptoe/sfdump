# FAQ

## What happens if the export is interrupted?

Re-run it. Existing files are skipped automatically.

## What if Salesforce returns zero-byte bodies?

Retry logic will catch and reattempt them.

## Can I use chunking and resuming together?

Yes. Chunking divides work; resume prevents re-downloads.

## Are unredacted reports stored in the repo?

No. They should go into a private folder outside Git.

## Do I need pandoc for PDF?

Only if you want PDF reports. Markdown reports always work.
