# ADR 0004: Report notification records and triage cancellation

Status: accepted

## Context

Issue #9 requires reassignment and ungrouping to cancel unsent operations and keep sent history. The delivery (#14) and dispatch (#15) work that will create those operations has not landed. An in-memory guard cannot prove durable cancellation.

## Decisions

- `ReportNotificationOperation` is the persisted record of one prepared employee notification for a report. It captures the problem, recipient membership, resolution revision, and report version at preparation time. Later delivery and dispatch work must extend this model, not add competing send state.
- It is not the spec's FollowUp. It has no report-plus-revision uniqueness because one follow-up may need several preparations. Customer-contact outcomes stay out of it.
- States are `draft`, `queued`, `failed`, `uncertain`, `sent`, and `cancelled`. Reassignment, a move to another problem, and ungrouping cancel `draft`, `queued`, and `failed` rows with a content-free reason in the same transaction as the report change.
- `sent` rows are never changed. `uncertain` rows keep their state and gain an invalidation, because the remote write may have happened; they need reconciliation before any resend.
- Rows are never retargeted. A fresh preview creates a new row. `stale_reason` checks the captured report version, problem, resolution revision, and recipient against current rows; senders call it immediately before the external write.
- Lock order is the report row, then its notification rows ordered by `(created_at, id)`. Senders must take locks in the same order.
- Report, problem, and recipient references use `PROTECT`, so notification history cannot be deleted by accident. Report deletion (#20) must decide what to retain.
- Database constraints tie `sent` to a send time and remote IDs, and allow an invalidation only on `cancelled` or `uncertain` rows.

## Not decided here

- Creating rows, preview, approval, sending, workers, leases, and retries belong to #14 and #15. No production path creates these rows yet; tests insert them directly.
- Cancellation cannot stop a remote request that is already executing. The sender's pre-write recheck and the `uncertain` state cover that window.

## Problem timelines

Linking, moving, ungrouping, and reassigning a linked report also write a problem-scoped activity with the report ID, so removal history survives on the problem. Activity written before this change exists only on report timelines and is not backfilled.
