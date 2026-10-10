# Workspace settings

Owners manage invitations, active membership roles, connections, allowed Slack
channels, and deletion in `/settings`. Members can read connection status.
Report deletion is in the report detail panel. The last active owner cannot be
removed or demoted.

## Operator setup

Set these outside the repository:

- `RESCRIBO_CREDENTIAL_KEY`: a Fernet key generated with
  `uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`.
  Keep it separate from the database and preserve it for restore.
- `RESCRIBO_SLACK_APP_ID`, `RESCRIBO_SLACK_CLIENT_ID`,
  `RESCRIBO_SLACK_CLIENT_SECRET`.
- `RESCRIBO_SLACK_SIGNING_SECRET`: the Slack App's signing secret. Verifies
  every request to `/api/integrations/slack/interactions/` and
  `/api/integrations/slack/events/`.
- `RESCRIBO_GITHUB_APP_ID`, `RESCRIBO_GITHUB_CLIENT_ID`,
  `RESCRIBO_GITHUB_CLIENT_SECRET`, `RESCRIBO_GITHUB_PRIVATE_KEY` (PEM text).
- `RESCRIBO_GITHUB_WEBHOOK_SECRET`: the secret configured on the GitHub App's
  webhook. Verifies `X-Hub-Signature-256` on `/api/integrations/github/webhook/`.
- `RESCRIBO_GITHUB_RECONCILIATION_INTERVAL_SECONDS`: issue refresh interval in
  seconds. Defaults to `900` (15 minutes).
- `RESCRIBO_PUBLIC_BASE_URL`: the externally reachable application origin.

Register the GitHub and Slack Apps as in [Provider app setup](PROVIDER_SETUP.md).
The provider callbacks and request URLs resolve connections to their workspace
or installation. Use HTTPS outside local development. Exclude callback query
strings and request bodies from proxy/application access logs. Never enable
provider debug logging.

Slack setup requests the scopes defined in `integrations/slack/policy.py`.
Channel approval verifies membership, channel type, and publication consent.
GitHub setup requires an installed App with Issues write and Metadata read.
Install the App on the target repository first, then enter `owner/repository`
and authorise a user with access. Changing repositories requires this same
verification and publication consent. Temporary GitHub installation tokens are
revoked after the settings request; setup user tokens are not persisted.

OAuth state expires after ten minutes and is bound to the owner, workspace,
provider and browser session. State is single-use even if the provider exchange
fails. Stored Slack tokens use authenticated Fernet encryption. API responses
never contain provider credentials.

## Disconnect and deletion

Disconnect clears stored credentials and the installation binding, removes
allowed channels, and invalidates unfinished setup. Draft, queued and failed
notification operations are cancelled. Uncertain operations remain uncertain
and become invalidated; sent history and reports remain. Reconnecting does not
restore approvals. App-wide keys belong to the operator and are not deleted by
a workspace disconnect. Disconnect does not uninstall a shared upstream App.

Report deletion removes the report, snapshot, notification operations and
report-related activity, leaving only a content-free deletion event. The
problem and upstream content remain. Workspace deletion removes its primary
records, credentials, memberships and invitations. It first revokes the Slack bot
token with Slack; if Slack fails, deletion still completes. The GitHub App is not
uninstalled, because other workspaces may share the installation. Shared user
accounts and other workspaces remain. Neither action deletes Slack messages or
GitHub issues.

Successful inbound webhook receipts keep their payload for seven days. After that
only the provider, delivery ID, event, status, and timestamps remain, so
redeliveries are still recognised as duplicates.

## Backup and restore

Keep backups for 30 days unless you set a different policy. Deleted reports and
workspaces stay in backups until those backups expire; deletion does not erase
them. Local dumps in `backups/` hold tenant data, so delete them on the same
schedule.

- `task backup` writes a `pg_dump` custom-format dump to `backups/`.
- `task restore-check [DUMP]` restores the newest dump, or the one given, into a
  throwaway database. It checks that no migration is pending, reads a restored
  report through the API as its owner, then drops the database. It fails if the
  dump has no report.

Last run: 2026-10-05, local data, PostgreSQL 17. Backup and restore check passed.

## Integration boundaries

This PR supplies persisted connection settings and the existing notification
operation cancellation rules. GitHub issue link, create, receipt, and sync
records are described in [the GitHub workflow guide](GITHUB_WORKFLOW.md).
Slack notification delivery (#14), the general durable operation lifecycle
(#15), and retention/restore (#20) remain separate work. No matching records
exist yet; their deletion must be connected when #23 introduces them.

New senders must recheck active membership, connection status/binding and
notification validity immediately before provider IO. Use the lock order
workspace, connection, report, notification. GitHub operations must mint only
repository-restricted tokens from a currently active binding; never retain a
usable token outside that guarded operation. Channel capture must revalidate
approval at use time. Settings checks do not count as issue reconciliation.
GitHub operation counts include queued, running, failed, and uncertain issue
creates. They do not include draft previews.

Automated provider tests mock SDK/API responses. They do not verify a live OAuth
installation or a live send. Browser tests use a separate synthetic workspace.
