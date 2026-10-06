# Design

## Context

- Every workspace API route is scoped by `workspace_id` and checks membership, so a user with one demo membership already sees only the demo.
- Invitations, member changes, password resets, workspace deletion, and connection settings are owner-only views. Members cannot change their own password or email.
- Slack writes already have a fake client (`integrations/slack/fake_delivery.py`), switched on for the whole process by `RESCRIBO_SLACK_FAKE_DELIVERY` for browser tests.
- GitHub work starts from HTTP use cases (link, refresh, create draft, recovery) and from workers (create, sync, reconciliation, revalidation, recovery). Sync is triggered by webhooks, the 15-minute reconciliation, and the dispatcher.
- `seed_test_accounts` shows the seeding pattern. `delete_workspace` holds the only record deletion order that respects `PROTECT` references.
- Match suggestions are off globally until the evaluation gate passes. Matching itself is the local Rust matcher.

## Goals / Non-Goals

**Goals:**
- One place answers "is this a demo workspace", and every provider path asks it.
- A missed path still fails before the network.

**Non-Goals:**
- Simulating GitHub. Issue creation, linking, refresh, and recovery are refused in the demo; seeded issues show the linked states.
- Per-visitor accounts or public signup.
- Deployment. Hosting notes belong to #89.

## Decisions

- **Flag, not slug.** `Workspace.is_demo` marks the demo. A slug convention would break on rename and could match a real workspace.
- **One check, translated per layer.** `accounts/demo.py` exposes `is_demo_workspace(workspace_id)` and the user-facing detail. Connection services raise their existing `SetupError` with `demo_workspace`; feedback use cases raise a new `DemoWorkspace` error that `feedback/http.py` maps to 400. Workers skip or cancel. Alternative: middleware that blocks routes by path. Rejected because it misses workers and couples the rule to URLs.
- **Simulate Slack per send.** The send path already loads the workspace. `SendContext` gains `simulated`, and the Slack client functions take it to pick the existing fake client. The rest of the state machine runs unchanged, so a demo send ends `sent` with activity like a real one. The UI labels delivery results "Simulated" whenever the session's workspace is a demo. Every demo result is simulated, so no new column is needed.
- **Refuse GitHub, skip it in workers.** Simulating issue creation would need invented issue URLs, which could point at real repositories. Workers return early for demo workspaces, and reconciliation leaves them out. The seeded GitHub connection uses installation ID `demo`, which `create_installation_token` rejects as non-numeric before any request. The Slack connection uses team `TDEMO` and a credential that does not decrypt, so a missed Slack path fails locally too.
- **Purge shared with deletion.** Extract the ordered content deletion from `delete_workspace` into `purge_workspace_content(workspace)`, in a refactor commit. Deletion calls it and then removes the workspace; the demo reset calls it and keeps the workspace, memberships, and connections, so visitor sessions survive a reset.
- **Seed through use cases.** `feedback/demo.py` builds reports, problems, triage mistakes, state changes, fix confirmation, and follow-ups through the domain functions, so the data obeys the same rules as real use. It writes rows directly only for states that need a provider failure: failed and uncertain notifications, an uncertain GitHub creation, and linked issues.
- **Accounts.** The visitor `demo@example.com` is a member. Its password comes from `RESCRIBO_DEMO_PASSWORD`; without it, the first seed generates one and prints it, and later resets leave it alone. The owner `demo-owner@example.com` has an unusable password, so no owner credential exists. The seed refuses to run if either email belongs to another workspace, or if the `demo` slug belongs to a workspace that is not a demo.
- **Nightly reset.** A beat task runs the seed at 03:00 UTC when a demo workspace exists, and does nothing otherwise. It never creates a demo.

## Risks / Trade-offs

- [A new provider path forgets the check] → The non-numeric installation ID and the undecryptable Slack credential make a missed call fail locally. Tests cover each current path.
- [Visitors cannot see owner screens] → #89's walkthrough can show settings and members.
- [A visitor's edits vanish at the nightly reset] → Expected for a shared demo; the demo label says the data is fictitious.
