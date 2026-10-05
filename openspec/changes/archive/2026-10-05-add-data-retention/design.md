# Design

## Context

See proposal.md for motivation. The local scaffold runs PostgreSQL 17 in the `postgres` Compose service, and the host has no PostgreSQL client tools. `docs/SETTINGS.md` says only that backups follow the operator's policy. Workspace deletion clears the stored Slack token without telling Slack.

## Goals / Non-Goals

**Goals:**
- A backup and restore path anyone can run locally with one command each.
- A restore check that fails loudly when a dump is unusable.

**Non-Goals:**
- Scheduled backups, off-site storage, or pruning dumps after 30 days. Retention is the operator's policy; the docs state the default.
- Revoking or uninstalling the GitHub App.

## Decisions

### Run pg_dump and pg_restore inside the Compose service
`task backup` runs `docker compose exec -T postgres pg_dump -Fc` and writes the dump to a gitignored `backups/` directory on the host. `task restore-check` pipes the dump into `pg_restore` in the same container. This needs no host tools and matches the server version.

Alternative: require host PostgreSQL client tools. Rejected because versions can drift from the server and it adds a setup step.

### Restore into a throwaway database on the same server
`task restore-check` creates a uniquely named database, restores into it, and drops it when it exits, pass or fail. The working database is never touched.

### Check the restore through Django, not a running server
A management command, run with `RESCRIBO_DATABASE_URL` pointing at the throwaway database, does the checks:
1. `migrate --check` style verification that no migration is unapplied.
2. Find an owner membership and a report in its workspace. Fail if there is none.
3. Read that report through the Django test client as the owner, using the same API route the frontend uses. Fail on anything but HTTP 200 with the report's ID.

Alternative: start the API server and call it over HTTP. Rejected because it adds port and process handling for no extra coverage of the restore itself.

### Revoke the Slack token best effort, outside the deletion transaction
Workspace deletion first checks that the actor is an owner and the confirmation matches the slug, so a rejected request never revokes anything. It then reads and decrypts the Slack token, calls `auth.revoke`, logs a content-free warning on failure, and runs the existing deletion transaction, which repeats both checks under its locks. The Slack call happens before the transaction so no row lock is held across a network call. The token is only cleared after the call returns.

### Purge receipts with a periodic task
A beat task updates succeeded receipts with `received_at` older than seven days in one query, clearing the payload and identifier columns. Deduplication keeps working because it relies on the unique provider and delivery ID, which stay.

## Risks / Trade-offs

- [Revocation succeeds but the deletion transaction fails] → The workspace stays with a revoked token. The connection then fails closed on its next Slack call, and the owner can retry deletion.
- [The restore check passes on a dump with no reports] → It fails instead, because step 2 requires a report. Run it against a database with real local data.
- [Dumps in `backups/` hold tenant data] → The directory is gitignored, and the docs say to delete local dumps under the same retention.
