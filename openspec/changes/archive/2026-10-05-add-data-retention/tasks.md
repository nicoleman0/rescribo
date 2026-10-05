# Tasks

## 1. Receipt retention

- [x] 1.1 Add a periodic task that clears `normalized`, `action`, `installation_id`, `repository_id`, and `issue_id` on succeeded receipts received more than seven days ago, and schedule it in `CELERY_BEAT_SCHEDULE`. Verify with a test that old succeeded receipts are cleared and recent ones are not.
- [x] 1.2 Test that a redelivery with a purged delivery ID is still recognised as a duplicate, and that pending and failed receipts keep their payload.

## 2. Slack revocation on workspace deletion

- [x] 2.1 Add a token revocation call (`auth.revoke`) to the Slack client. Verify with a unit test against a mocked Slack SDK.
- [x] 2.2 Call it best effort in workspace deletion before credentials are cleared. Verify with tests for successful revocation, a Slack failure that still deletes the workspace, a wrong confirmation that revokes nothing, and a workspace with no Slack connection.
- [x] 2.3 Update the deletion section of `docs/SETTINGS.md`. Verify it states that the Slack token is revoked and the GitHub App is not uninstalled.

## 3. Backup and restore

- [x] 3.1 Add `task backup` that writes a `pg_dump` custom-format dump, and document the 30-day default retention and the backup caveat in `docs/SETTINGS.md`. Verify the task writes a dump file.
- [x] 3.2 Add `task restore-check` that restores a dump into a throwaway database, checks migrations are current, reads a restored report through the API, and drops the database. Verify it fails on an empty database dump.
- [x] 3.3 Run `task backup` and `task restore-check` against local data. Verify both pass and record the date and result in `docs/SETTINGS.md`.

## 4. Checks

- [x] 4.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 4.2 Run `task check test build schema-check` and `task worker-check` with PostgreSQL and Redis running, and verify both pass.
