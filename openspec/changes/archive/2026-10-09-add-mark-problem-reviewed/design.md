# Design

## Context

- `Problem.needs_review` is set by `_flag_problem_needs_review` (`backend/feedback/follow_ups.py`, reason `still_affected_outcome`) and by issue close and reopen in `backend/feedback/engineering_issues.py` (reasons `issue_closed`, `issue_reopened`). Each writes `problem.updated` with `metadata={"fields": [...], "reason": ...}`.
- Only `confirm_fix` in `backend/feedback/problems.py` clears it, as one field among the fix fields, and it writes `problem.fix_confirmed`, not `problem.updated`.
- Problem edits follow one shape: `locked_problem`, `require_version`, change fields, `finish_mutation`, `write_activity`. Views subclass `ProblemActionView`, which maps `FeedbackError` to responses and returns the current problem with each 409.
- `ProblemActivitySerializer.get_metadata` exposes an allowlist per action. Today only `tag_name` for `problem.fix_release_linked`. `describeUpdate` in `frontend/src/features/problems/activity-format.ts` reads any entry whose `changed_fields` include `needs_review` as "flagged the problem for review".
- `ProblemNextStep` is display-only and shows the "Review the fix" banner when `needs_review` is true, except for `not_planned` problems, which get the "Not planned" banner first.

## Goals / Non-Goals

**Goals:**
- One action that clears the flag in any state, with the same version check, workspace scope, and 409 shape as other problem edits.
- Activity that says who reviewed it, without misreading older entries.

**Non-Goals:**
- Showing why a problem was flagged. The reason is now exposed in activity metadata but the banner text does not use it.
- Changing what sets the flag, or confirming a fix from `fix_available`.
- Layout, dates, and labels elsewhere (#99).

## Decisions

### D1. Use case `mark_problem_reviewed` in `problems.py`
`mark_problem_reviewed(*, actor, problem_id, expected_version, now=None) -> Problem`: lock with `locked_problem`, `require_version`, raise `InvalidTransition(action="mark_reviewed", from_state=problem.state)` when `needs_review` is false, set it false, `finish_mutation(update_fields=["needs_review"])`, write `problem.updated` with `{"fields": ["needs_review"], "reason": "reviewed"}`.
- `confirm_fix` keeps its own assignment. Extracting a helper for one boolean assignment would add indirection without removing a rule; the shared knowledge is the mutation shape, which both already use.
- `InvalidTransition` over `NoChanges`: the action is unavailable, not a no-op edit. Both map to 409 with the current problem; the frontend already words `invalid_transition` as "no longer available".
- Any member may act. No role check, matching other problem edits.

### D2. Reuse `problem.updated` with a `reason`
- The maintainer chose `problem.updated`. The clearing entry is told apart by `metadata.reason == "reviewed"`, the same key the flagging paths use. No new `Activity.Action` value, so no migration.
- `get_metadata` exposes `reason` for `problem.updated` entries when present. Alternative: store the new value (`"needs_review": false`). Rejected: a second convention beside the existing `reason` key.

### D3. API
- `POST /api/workspaces/<ws>/problems/<id>/mark-reviewed/`, body `{expected_version}`, response `ProblemDetail`. 409 `invalid_transition` or `version_conflict` with `current`, 404 for another workspace.
- `ProblemMarkReviewedView(ProblemActionView)` with `MarkReviewedSerializer(VersionedSerializer)` so the OpenAPI request has its own name, as `UnlinkFixReleaseSerializer` does.
- The route goes in `backend/config/urls.py`, a shared file; the coordinator approved the one line.

### D4. Activity wording
`describeUpdate(fields, reason?)`: when `fields` includes `needs_review` and `reason === 'reviewed'`, the needs-review part reads "marked the problem reviewed"; otherwise "flagged the problem for review" as today. Entries without a reason keep their current text.

### D5. Banner button
- `ProblemNextStep` takes `workspaceId` and owns the mutation through `useProblemMutation(workspaceId, () => markProblemReviewed(...))`, as `FixCard` owns its unlink mutation. `problem-detail-page.tsx` passes `workspaceId`.
- "Mark reviewed" is an outline `sm` button with `touchTarget`, after the two link buttons, shown on the review step and on the "Not planned" step when `needs_review` is true. Label while pending: "Marking reviewed…", disabled while pending. Not disabled in the demo: no external call is made.
- `ActionError` ("The problem was not marked reviewed", record `problem`) renders under the buttons whenever the mutation has an error, on any step. A 409 swaps the banner to the current problem's step, and the error must stay visible there.
- On success, focus moves to the banner heading (`tabIndex={-1}`), since the button that had focus is gone.
- The review body gains a closing sentence: fixed, "Check the follow-up outcomes and the GitHub issue, then mark the problem reviewed."; otherwise, "Check the GitHub issue, then confirm the fix under Fix or mark the problem reviewed."

### D6. Not planned and flagged
A `not_planned` problem can be flagged (an issue closes after the decline). Its banner stays "Not planned", in the same order, and gains the "Mark reviewed" button while `needs_review` is true. It has no link buttons, since it has no follow-ups. After success the flag and the button are gone and the banner is unchanged. The backend allows the action in any state.

## Risks / Trade-offs

- Marking reviewed in the demo clears the flag for every demo visitor until `seed_demo` runs again. The e2e suite must not mark the demo problem reviewed.
- Exposing `reason` shows internal reason codes in the API (`issue_closed`, `still_affected_outcome`, `issue_reopened`, `reviewed`). They are stable strings already stored; the frontend reads only `reviewed`.
