# Proposal

Delivers GitHub issue #181.

## Why

The problems spec lets members start, stop, decline, and reopen a problem, and `change_problem_state` implements it, but no endpoint or screen calls it. A problem left with no reports shows "No reports" and gives the member no way to close it out.

## What Changes

- A problem state endpoint for start, stop, decline with a reason, and reopen. It reuses `change_problem_state`, with version checks, activity, and workspace scoping.
- Problem detail returns the decline reason of a `not_planned` problem.
- A Status card on problem detail. It shows the current state, the reason when not planned, and the actions the state allows. Declining asks for a reason in an inline confirm step.
- On an `open` or `in_progress` problem with no linked reports, the linked reports section offers to mark it not planned.
- `fix_available` is out of scope. Fix confirmation already covers it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `problems`: adds requirements for changing state from problem detail, showing the decline reason, and offering to decline a problem with no reports. The existing "Problem lifecycle" rules are unchanged.

## Impact

- Backend: `backend/feedback/views.py`, `backend/feedback/serializers.py`, `backend/config/urls.py`, new API tests, and one row in the workspace isolation route table.
- API: one new route, one new request schema, one new response field (`not_planned_reason`). Regenerated `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`.
- Frontend: `frontend/src/api/problems.ts` and `frontend/src/features/problems/`.
- No migration. The model already has `not_planned_reason`.
