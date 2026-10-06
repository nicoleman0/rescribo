# Proposal

## Why

Report and workspace deletion exist, but inbound receipt payloads are kept forever, workspace deletion leaves the Slack bot token valid at Slack, and backup retention and restore are undocumented and untested. Delivers #20 in milestone C.

## What Changes

- Purge successful inbound receipts within seven days: clear the normalized payload and the action, installation, repository, and issue identifiers, keeping only provider, delivery ID, event, status, and timestamps for deduplication.
- Workspace deletion revokes the Slack bot token with Slack, best effort, before clearing it. Deletion completes even if Slack fails. GitHub installations are not uninstalled, because other workspaces may share them (#74).
- Document a 30-day default backup retention that the operator can change, and state that deleted data persists in backups until they expire.
- Add `task backup` and `task restore-check`, and run the restore check once.

Already built and specified in `data-protection`: capture-context expiry, report deletion, workspace record removal, and disconnect.

## Capabilities

### New Capabilities

### Modified Capabilities
- `data-protection`: adds receipt payload retention, Slack token revocation on workspace deletion, and documented backup and restore

## Impact

`operations` receipt purge as a periodic Celery task; `integrations/slack/client.py` and `feedback/deletion.py` for revocation; `Taskfile.yml` and a restore script; `docs/SETTINGS.md` for deletion, backup, and restore.
