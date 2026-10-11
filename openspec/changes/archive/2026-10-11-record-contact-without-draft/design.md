# Design

## Context

Checked in the code at f75904d:

- `follow-up-detail.tsx:229` renders `ContactSection` only when `notification && notification.state !== 'cancelled'`. The API never returns a cancelled notification (`current_notification` excludes them), so the second half is dead and the real rule is "a notification exists".
- `record_outcome` and `correct_outcome` in `backend/feedback/follow_ups.py` never read the notification. `test_recorded_contacted_moves_row_to_contacted_bucket` already records with no notification.
- `backend/connections/slack_outcomes.py`: `_resolve_target` returns `operation = None` when there is no live notification and `handle_outcome_action` then skips the DM update. `test_reassigned_recipient_can_record_outcome_from_slack` covers it. No server path needs a notification before an outcome.

So the fix is in the page only.

## Buckets after contact with no notification

`search_follow_ups` places a follow-up by contact state once contact is not `pending`:

| Contact | Notification | Bucket | Row shows |
| --- | --- | --- | --- |
| pending | none | Needs approval | Not prepared / Pending |
| contacted | none | Awaiting confirmation | Not prepared / Contacted |
| confirmed, still_affected, no_response | none | Completed | Not prepared / (outcome) |
| contacted or terminal | draft | same as above | Draft / (outcome) |

No bucket query changes. No count is wrong: the follow-up leaves Needs approval when contact is recorded, and it never enters Awaiting contact, which needs a sent message. The only odd reading is a Completed row with delivery "Not prepared" or "Draft". Both are true statements, and `web-interface` "Labelled follow-up statuses" requires "Not prepared" for a follow-up with no message.

## Decisions

1. **Always render the contact section.** Remove the condition, not replace it. The server already enforces who may record.
2. **Leave an unsent draft alone when an outcome is recorded** (open question 1). The spec says contact is independent of delivery, and `record_outcome`'s docstring promises it never changes the notification row. Cancelling would need a new invalidation reason in `models.py` (shared file, migration) and would discard an edited draft if an owner later corrects the outcome back to pending.
3. **Message section with no message and a recorded outcome: keep "Prepare message", add one sentence** (open question 2). The employee may still want the fix note sent to the recipient. The sentence replaces nothing: "Customer contact is already recorded. Prepare a message only if <recipient> still needs it."
4. **No bucket or label change.** See the table.

## Open questions for the maintainer

1. Unsent draft when an outcome is recorded: leave it (planned), cancel it, or show it differently.
2. Message section once contact is recorded with no message: keep the prepare button with a sentence (planned), leave it unchanged, or hide the button.

Tasks 3.2 and the last two spec scenarios follow the planned answers and change if the answers differ.

## Risks

- A member who may not record (not owner, assignee, or submitter) now sees the form on every follow-up and gets the existing 409 on submit. This already happens once a draft exists. The detail payload carries no permission flag; adding one is an API change and out of scope. Flagged for a separate issue.
- #157 edits `RecipientForm` in the same file and adds a test to the same e2e file. This change touches `FollowUpBody` and `DraftSection` only and appends its tests, so the rebase stays mechanical.

## Noted, not changed

A follow-up that is `pending` with a `queued` message is in no bucket except All (`needs_approval` excludes queued, `awaiting_contact` needs sent). It predates this change.
