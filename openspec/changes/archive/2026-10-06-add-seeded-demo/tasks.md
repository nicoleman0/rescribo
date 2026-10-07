# Tasks

## 1. Demo flag

- [x] 1.1 Add `is_demo` to `Workspace` with a migration, default false. Verify with a model test that existing workspaces stay non-demo and `task schema-check` passes.

## 2. Seed data and demo accounts

- [x] 2.0 Extract the ordered content deletion from `delete_workspace` into `purge_workspace_content`, with no behaviour change. Verify the existing deletion tests pass unchanged.
- [x] 2.1 Add a `seed_demo` command, following `seed_test_accounts`, that creates or resets the demo workspace with fictitious companies, reports, problems, linked issues, follow-ups, mistakes, and failed and uncertain operations. Verify with a test that runs it twice, finds every main workflow state, and leaves other workspaces unchanged.
- [x] 2.2 Seed one member-role visitor account, whose sign-in details the command prints, and an owner account whose credentials it never prints. Both belong only to the demo workspace. Verify with API tests that the visitor gets 404 for a private workspace and is refused invitations, member changes, password resets, and workspace deletion, and that the command output contains no owner credentials or other workspace names.
- [x] 2.3 Add a nightly beat task that re-runs the demo seed when a demo workspace exists. Verify with a test that edits demo reports and problems, runs the task, finds the seeded state restored and other workspaces unchanged, and with `task worker-check` that the task registers.

## 3. No real integrations

- [x] 3.1 Add one demo guard at the provider boundary. Call it from Slack delivery, GitHub issue creation, issue link and refresh, connection setup, Slack revocation on workspace deletion, and scheduled reconciliation and sync. Verify with a test per path that the provider client is never called.
- [x] 3.2 Simulate Slack follow-up sends in the demo and label delivery results as simulated; refuse GitHub creation, linking, refresh, and recovery with the demo message. Verify that approving a demo follow-up ends sent with no Slack request, that the follow-up page shows the simulated label, and that each GitHub action returns the demo error.
- [x] 3.3 Reject integration setup in the demo with a clear message in the API and settings page. Verify with an API test and a frontend test.
- [x] 3.4 Keep match suggestions off in the demo. Verify the demo inbox shows none.

## 4. Demo label

- [x] 4.1 Expose `is_demo` in the session or workspace API and run `task schema`. Verify `task schema-check` passes.
- [x] 4.2 Show the demo label in the app shell, so every screen has it. Verify with an `app-shell` unit test and an e2e check on the inbox.

## 5. Checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check`, `task e2e`, and `task worker-check`. Verify all pass.
