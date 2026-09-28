# GitHub issue workflow

## App setup

Install the GitHub App on the repository selected in workspace settings. It needs Issues read/write and Metadata read. Subscribe to **Issues**; installation and installation repository lifecycle events are delivered automatically.

Set `RESCRIBO_GITHUB_WEBHOOK_SECRET` to the App webhook secret and register:

```text
{origin}/api/integrations/github/webhook/
```

The receiver checks `X-Hub-Signature-256` over the raw body, stores only normalized routing and lifecycle fields, then acknowledges. It does not call GitHub. Keep the app worker and Beat scheduler running with the API.

## Background work

Beat publishes due receipts, issue creates, and issue sync requests every 60 seconds. It queues a reconciliation pass every `RESCRIBO_GITHUB_RECONCILIATION_INTERVAL_SECONDS` seconds (900 by default). PostgreSQL holds work state and leases, so a broker outage leaves committed work available for dispatch after service returns. Duplicate task delivery is expected.

A successful pass advances `last_reconciled_at` only after every issue captured for that connection and binding has a successful current read. Failed reads retain the previous state and last successful timestamp. Issue state and access state are displayed separately.

## Create approvals and uncertain results

Preview creates a private draft record with a 15-minute expiry. It has no GitHub side effect. Approval freezes the displayed title and body, then queues one create operation. The operation UUID is included as an HTML comment marker so the worker can find a remote issue if its response or local commit is lost.

An uncertain operation is never posted again automatically. Use **Check creation result** to scan every page of open and closed issues for the marker. A supplied issue reference is also checked against the bound stable repository ID and marker. No match is inconclusive because GitHub listing can lag. Multiple matches or a removed marker also remain uncertain and require operator investigation.

## Lifecycle limits

A fetched closure sets `needs_review`; it does not confirm a fix. A verified reopen after fix confirmation returns a fixed problem to `in_progress` and invalidates unsent notification approvals. Sent history is preserved.

Polling converges to the current GitHub state. It cannot reconstruct a close/reopen cycle that occurred entirely between successful reads and ended in the original state. A signed, newer reopen event can preserve that evidence when GitHub delivered it.

## Verification boundary

Backend tests use PostgreSQL, Redis, and synthetic provider responses. Browser route mocks prove UI behavior only. Neither proves a live App installation or webhook delivery. Live verification must use a designated disposable repository and record sanitized observations separately from test output. See [the feasibility checks](GITHUB_ISSUE_LIFECYCLE_CHECK.md) for provider setup; they do not exercise this product workflow.
