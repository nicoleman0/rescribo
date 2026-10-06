# Tasks

## 1. Binding

- [x] 1.1 Test that a second workspace binds an installation and repository already bound elsewhere, and that its settings response names only its own connection with no hint of the other workspace. Verify with a new test in `backend/tests/test_settings.py`.

## 2. Webhook fan-out

- [x] 2.1 Test that an issue event for a shared repository syncs the issue in the workspace that linked it and creates nothing in a workspace that did not. Verify with a new test in `backend/tests/test_engineering_issue_webhook.py`.
- [x] 2.2 Test that when both workspaces linked the same GitHub issue, one event updates each workspace's own issue and problem independently. Verify in the same file.
- [x] 2.3 Test that an installation deletion event marks both connections and both workspaces' linked issues access lost. Verify in the same file.

## 3. Disconnect

- [x] 3.1 Test that disconnecting GitHub in one workspace leaves the other connection active and its linked issue still syncing on the next issue event. Verify with a new test in `backend/tests/test_engineering_issue_webhook.py`.

## 4. Gaps found by the tests

- [x] 4.1 If any test above exposes a leak or cross-workspace effect, fix it in the owning module and verify that test passes. If none does, note that in the PR. (None did.)

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 5.2 Run `task check test build schema-check` with PostgreSQL and Redis running and verify it passes.
