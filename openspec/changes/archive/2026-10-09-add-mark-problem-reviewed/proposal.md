# Proposal

Delivers GitHub issue #113, Let a member mark a flagged problem as reviewed.

## Why

A problem is flagged for review when its GitHub issue closes or reopens, or when a customer says they are still affected. Only confirming a fix clears the flag, and that is possible only from `open` or `in_progress`. A flagged `fix_available` problem keeps the flag forever, as the demo's "Password reset emails" problem shows.

## What Changes

- A workspace member can mark a flagged problem reviewed. This clears `needs_review` in any problem state. It is refused when the problem is not flagged.
- The action is version-checked and workspace-scoped, like other problem edits.
- Marking reviewed writes a `problem.updated` activity entry with the member as actor. Activity reads "marked the problem reviewed". Older flag entries still read "flagged the problem for review".
- The "Review the fix" next-step banner gets a "Mark reviewed" button. A flagged `not_planned` problem shows the button on its "Not planned" banner. After it succeeds the banner shows the next step for the problem's state.
- No new activity action and no migration.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `problems`: adds a requirement for clearing the review flag by hand.
- `web-interface`: adds a requirement for the Mark reviewed button on the next-step banner and how activity describes it.

## Impact

- Backend: a `mark_problem_reviewed` use case in `backend/feedback/problems.py`, a `ProblemMarkReviewedView` in `views.py`, a request serializer, and activity metadata exposure in `ProblemActivitySerializer`.
- Shared files approved by the coordinator: `backend/config/urls.py` (one route) and `frontend/e2e/follow-ups.spec.ts` (one test).
- API contract: regenerated `openapi.yaml` and `frontend/src/api/schema.d.ts`.
- Frontend: `markProblemReviewed` in `frontend/src/api/problems.ts`, the button in `problem-next-step.tsx`, the label in `activity-format.ts` and `problem-activity.tsx`, `problem-detail-page.tsx` passing the workspace ID.
- Tests: backend service, API, and cross-workspace cases; frontend unit tests. One e2e case in `frontend/e2e/follow-ups.spec.ts`, reusing its saved session.
