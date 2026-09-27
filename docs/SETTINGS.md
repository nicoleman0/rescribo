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
- `RESCRIBO_GITHUB_APP_ID`, `RESCRIBO_GITHUB_CLIENT_ID`,
  `RESCRIBO_GITHUB_CLIENT_SECRET`, `RESCRIBO_GITHUB_PRIVATE_KEY` (PEM text).
- `RESCRIBO_GITHUB_WEBHOOK_SECRET`: the secret configured on the GitHub App's
  webhook. Verifies `X-Hub-Signature-256` on `/api/integrations/github/webhook/`.
- `RESCRIBO_PUBLIC_BASE_URL`: the externally reachable application origin.

Register each workspace's callback URL with the relevant application:
`{origin}/api/workspaces/{workspace-id}/connections/slack/callback/` and
`{origin}/api/workspaces/{workspace-id}/connections/github/callback/`.
Register `{origin}/api/integrations/github/webhook/` as the GitHub App's webhook
URL; it is shared by every workspace and resolves the connection from the
delivery's installation ID.
Use HTTPS outside local development. Exclude callback query strings and request
bodies from proxy/application access logs. Never enable provider debug logging.

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
records, credentials, memberships and invitations. Shared user accounts and
other workspaces remain. Neither action deletes Slack messages or GitHub issues.
Backups follow the operator's retention policy; deletion does not immediately
erase backups.

## Integration boundaries

This PR supplies persisted connection settings and the existing notification
operation cancellation rules. Production capture (#12), issue sync (#10),
delivery (#14), durable operation dispatch (#15), and retention/restore (#20)
remain separate issues. No matching records exist yet; their deletion must be
connected to these use cases when #23 introduces them.

New senders must recheck active membership, connection status/binding and
notification validity immediately before provider IO. Use the lock order
workspace, connection, report, notification. GitHub operations must mint only
repository-restricted tokens from a currently active binding; never retain a
usable token outside that guarded operation. Channel capture must revalidate
approval at use time. Settings checks do not count as issue reconciliation.
GitHub operation counts are zero until issue operations are persisted.

Automated provider tests mock SDK/API responses. They do not verify a live OAuth
installation or a live send. Browser tests use a separate synthetic workspace.
