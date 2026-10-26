# Design

## Context

`can_record_outcome(*, actor, report)` in `backend/feedback/follow_ups.py` is the one home of the web app rule. Two callers use it: the web branch of `record_outcome`, and `FollowUpDetailSerializer.get_can_record_outcome` (#183). The Slack branch of `record_outcome` has its own check: an active actor who is `follow_up.recipient_id`, with a Slack identity and an active connection. `change_recipient` bumps the follow-up's version, so an open page from before the change submits a stale version.

## Goals / Non-Goals

**Goals:**
- One function decides web recording for both callers, with the recipient clause added.

**Non-Goals:**
- Merging the Slack check into the same function. Slack also needs the linked identity and the active connection, and its rule does not change.
- An e2e test for the new clause. The rule lives on the server and the page only reads the boolean, which #183's component tests already cover.

## Decisions

- **Signature `can_record_outcome(*, actor, follow_up, report)`.** The recipient lives on the follow-up; the assignee and submitter live on the report. `record_outcome` already holds both rows, locked. Passing only the follow-up and reading `follow_up.report` would issue a second, unlocked query for a row the caller already has. The function asserts `follow_up.report_id == report.pk`, so a caller cannot mix rows. The serializer passes `follow_up` and `follow_up.report`, which the detail queries already select.
- **The recipient clause compares `follow_up.recipient_id == actor.pk`.** Memberships are per workspace, and both callers load the follow-up filtered by `actor.workspace_id`, so a member of another workspace never reaches the check. A test still covers it.
- **No Slack link needed for the web clause.** The web app trusts the signed-in active membership, as it does for the assignee and submitter. A recipient who loses the Slack link can still record in the web app.
- **Line text: "Only an owner, the report's assignee or submitter, or the follow-up's recipient can record customer contact."** It keeps the old line's start and names the new clause. The maintainer chose it.

## Risks / Trade-offs

- [The previous recipient keeps the right through the assignee or submitter clause, which can look like the reassignment had no effect.] → Intended: the maintainer's rule is a union of clauses. The spec scenario only removes the right when no other clause applies.
