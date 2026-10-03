# Proposal

## Why

Report and workspace deletion exist, but inbound receipt payloads are kept forever and backup retention and restore are undocumented and untested. Delivers #20 in milestone C.

## What Changes

- Purge the normalized payload of successful inbound receipts within seven days, keeping only deduplication and status metadata.
- Document backup retention, stating that deletion does not immediately erase backups.
- Document and run a restore smoke test.

Already built and specified in `data-protection`: capture-context expiry, report deletion, workspace deletion, and disconnect.

## Capabilities

### New Capabilities

### Modified Capabilities
- `data-protection`: adds receipt payload retention and documented backup and restore

## Impact

`operations` receipt model and a periodic Celery task; operator documentation for backup and restore; a restore smoke script or Task target.
