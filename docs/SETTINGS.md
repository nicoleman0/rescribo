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
  `RESCRIBO_GITHUB_CLIENT_SECRET`.
- `RESCRIBO_GITHUB_PRIVATE_KEY`: the GitHub App's private key, in either of
  two forms:

  - the `.pem` file's full text with real newlines (as from a quoted shell
    value or a Compose multi-line value), or
  - one line with a literal `\n` between the PEM lines, as produced by
    `awk 'NF {printf "%s\\n", $0}' app.private-key.pem`.

  In `.env`, use the one-line form only: a multi-line value loads as its
  first line alone. An empty value means the GitHub App is not configured.
  A set value that is not an unencrypted RSA private key in PEM format stops
  every process at startup with a message naming this variable; the key text
  is never printed.
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

## Model provider

An owner connects one language model provider per workspace in Settings >
Connections. Pick OpenAI, Anthropic, Google, OpenRouter, or another
OpenAI-compatible server, then enter the model name and API key. Connecting
requires consent that conversation and report content from the workspace will
be sent to that provider. Rescribo then sends a fixed test prompt with no
workspace content and saves the connection only if the model returns JSON that
matches the test schema. Members can read the status, API style, base URL, and
model.

- Base URLs entered in Settings must be public `https://` URLs with no
  credentials, query, or fragment. Every new connection resolves the host,
  refuses it if any address is not public, and connects to the checked address.
  Redirects are not followed.
- The key is stored with the same Fernet encryption as Slack tokens and never
  returned by the API. Changing the base URL or provider needs a new key.
  Changing only the model keeps the stored key.
- Model calls go through `connections.model_access.model_client`. It refuses
  the demo workspace and any workspace without an active, consented connection.
- Outbound model calls ignore `HTTPS_PROXY` and the other proxy variables. A
  deployment that can reach the internet only through a proxy cannot use a
  model provider yet.

### Deployment default

An operator can set the provider for every workspace in `rescribo.toml`. Copy
`rescribo.toml.example` and uncomment one block. The file is read from the
repository root (`/app/rescribo.toml` in the image), or from the path in
`RESCRIBO_CONFIG_FILE`. With Compose, mount it into `backend`, `worker`, and
`scheduler`, for example `./rescribo.toml:/app/rescribo.toml:ro`.

- `api_key_env` names the environment variable that holds the key. The file
  never holds the key. Omit it for a local server with no key.
- Only this file may name an `http://` URL or a private host, such as Ollama,
  LM Studio, or vLLM on the same network.
- Settings shows the values locked. Each workspace owner still enables the
  provider with consent and a passing test.
- Every process checks the file at startup. An unknown key or API style, a
  missing field, a bad base URL, an unset or empty `api_key_env` variable, or a
  missing file at an explicit `RESCRIBO_CONFIG_FILE` stops startup with a
  message naming the file and the problem. The key is never printed.
- Adding or removing the `[model]` table stops existing workspace connections
  until an owner connects again, because their consent named another provider.

## Disconnect and deletion

Disconnect clears stored credentials and the installation binding, removes
allowed channels, and invalidates unfinished setup. Draft, queued and failed
notification operations are cancelled. Uncertain operations remain uncertain
and become invalidated; sent history and reports remain. Reconnecting does not
restore approvals. App-wide keys belong to the operator and are not deleted by
a workspace disconnect. Disconnect does not uninstall a shared upstream App.
Disconnecting the model provider deletes its key and the workspace's consent.
It does not cancel notifications.

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

Model provider tests mock the provider at the HTTP transport; no live model
call is part of the checks. Automated provider tests mock SDK/API responses. They do not verify a live OAuth
installation or a live send. Browser tests use a separate synthetic workspace.
