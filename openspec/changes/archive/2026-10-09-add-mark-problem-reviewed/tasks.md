# Tasks

Paths are from the repository root. Decisions D1 to D6 are in `design.md`.

## 1. Backend

- [x] 1.1 Add `mark_problem_reviewed(*, actor, problem_id, expected_version, now=None) -> Problem` to `backend/feedback/problems.py` per D1. Verify with new cases in `backend/tests/test_feedback_services.py`: clears the flag on a `fix_available` problem and on an `in_progress` one, leaves `state`, `fix_*` fields, and `resolution_revision` unchanged, bumps `version`, writes one `problem.updated` activity with the actor and `{"fields": ["needs_review"], "reason": "reviewed"}`; raises `InvalidTransition` when not flagged and `VersionConflict` on a stale version, writing no activity in either case.
- [x] 1.2 In `backend/feedback/serializers.py`, add `MarkReviewedSerializer(VersionedSerializer)` and make `ProblemActivitySerializer.get_metadata` return `{"reason": ...}` for `problem.updated` entries that have a reason (empty dict otherwise). Keep the `tag_name` branch unchanged.
- [x] 1.3 In `backend/feedback/views.py`, add `ProblemMarkReviewedView(ProblemActionView)` with `input_serializer = MarkReviewedSerializer` and `@extend_schema_view(post=problem_action_schema(MarkReviewedSerializer))`. Add `api/workspaces/<uuid:workspace_id>/problems/<uuid:problem_id>/mark-reviewed/` named `problem-mark-reviewed` to `backend/config/urls.py` beside `problem-assign-owner`. This file is shared; the coordinator approved the one route line.
- [x] 1.4 API tests in `backend/tests/test_feedback_api.py`: 200 returns `needs_review: false` and a higher `version`; the activity endpoint then returns the entry with `metadata.reason == "reviewed"` and the actor; 409 `invalid_transition` with `current` on an unflagged problem; 409 `version_conflict` with `current`; 400 without `expected_version`; a demo workspace member succeeds. Add `"problems/<uuid:problem_id>/mark-reviewed/": [("post", lambda ids: VERSION)]` to the route table in `backend/tests/test_workspace_isolation_api.py`, and a test that a foreign-workspace call returns 404 and leaves the flag set.
- [x] 1.5 Run `task schema` and keep the regenerated `openapi.yaml` and `frontend/src/api/schema.d.ts`. Verify `uv run python backend/manage.py makemigrations --check` reports no changes.

## 2. Frontend

- [x] 2.1 Add `markProblemReviewed(workspaceId, problemId, input: Schemas['MarkReviewed'])` to `frontend/src/api/problems.ts`, following `assignProblemOwner` (`csrf()` first, POST to `mark-reviewed/`).
- [x] 2.2 Change `describeUpdate` in `frontend/src/features/problems/activity-format.ts` to take `reason?: string` per D4, and pass `entry.metadata?.reason` from `problem-activity.tsx`. Verify in `activity-format.test.ts`: `['needs_review']` with `reason: 'reviewed'` reads "marked the problem reviewed"; with no reason, `'issue_closed'`, or `'still_affected_outcome'` it reads "flagged the problem for review"; `['state', 'needs_review']` with `'issue_reopened'` reads "changed the status and flagged the problem for review". Add one `problem-activity.test.tsx` case rendering "Demo Owner marked the problem reviewed".
- [x] 2.3 Update `frontend/src/features/problems/problem-next-step.tsx` per D5: `workspaceId` prop, the mutation, the Mark reviewed button on the review step and on a flagged "Not planned" step, the new body sentences, the `ActionError` on any step, and focus to the heading after success. Pass `workspaceId` from `problem-detail-page.tsx`. Verify in `problem-next-step.test.tsx` (wrap renders in a `QueryClientProvider`, mock `markProblemReviewed`): the button shows only when `needs_review`, including on a flagged `not_planned` problem, where the heading stays "Not planned"; clicking it sends the problem's `version`; after success with a `fix_available` result the heading reads "Fix available in …" and has focus; a 409 `invalid_transition` with a `current` problem shows "The problem was not marked reviewed" and the current problem's step.
- [x] 2.4 Add a "Mark reviewed" line to the Problem detail section of `frontend/DESIGN.md`: the review banner's only write action, and its error stays visible when the banner changes. This file is shared; append a bullet, do not reword existing ones.
- [x] 2.5 E2E, approved by the coordinator: in `frontend/e2e/follow-ups.spec.ts`, reusing its saved session, confirm a fix, record `Customer still affected` on the follow-up, open the problem, choose Mark reviewed, and assert the success banner, no Needs review badge, and the activity line. Add one test only. Do not mark the demo problem reviewed and do not sign in as the demo account.
- [x] 2.6 After screenshots: reseed the demo, run `.claude/skills/work-issues/scripts/shots.mjs` into `.claude/shots/after` (it shows the button on "Password reset emails"), then mark that problem reviewed in the UI on the dev server and capture the problem detail at 1280px light by hand into `.claude/shots/after/problem-detail-reviewed-desktop-light.png`. Build `.claude/shots/compare.html` with `compare.py`. Reseed the demo afterwards.

## 3. Repository checks

- [x] 3.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 3.2 `task check test build schema-check` passes with PostgreSQL and Redis running.
- [x] 3.3 `RESCRIBO_E2E_API_PORT=8113 RESCRIBO_E2E_FRONTEND_PORT=5113 task e2e` passes. Report any login throttle failure in `demo`, `motion`, or `themes` specs (#126) instead of working around it.

## Workflow follow-up

- Archive the change in the PR that completes it.
