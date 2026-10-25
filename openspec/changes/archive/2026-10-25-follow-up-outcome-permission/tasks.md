# Tasks

## 1. Make the rule public (no behaviour change, own commit)

- [x] 1.1 Rename `_can_record_outcome` to `can_record_outcome` in `backend/feedback/follow_ups.py` and update its one caller in `record_outcome`. Leave the Slack branch alone. Verify `uv run pytest backend/tests/test_follow_ups.py backend/tests/test_slack_outcomes.py` passes unchanged.

## 2. Backend field

- [x] 2.1 Add `can_record_outcome = serializers.SerializerMethodField()` after `history` on `FollowUpDetailSerializer`, typed as a boolean with `extend_schema_field`. The method calls `can_record_outcome(actor=self.context["actor"], report=follow_up.report)` and has no fallback for a missing actor.
- [x] 2.2 Pass `context={"actor": self.membership}` (or `actor`) to every `FollowUpDetailSerializer(...)` in the follow-up views, including the 409 `current` callables and `_follow_up_current`. Do not reorder or merge call sites. Verify with `grep -n "FollowUpDetailSerializer(" backend/feedback/views.py` that every hit has the context.
- [x] 2.3 Add API tests in `backend/tests/test_follow_ups.py` for `GET follow-ups/<id>/`: owner who is neither assignee nor submitter gets `true`; a non-owner assignee gets `true`; a non-owner submitter gets `true`; another member gets `false`. Verify they pass.
- [x] 2.4 Add an API test that another member's `POST .../outcome/` still returns 409, leaves `contact_state` at `pending`, and the body's `current.can_record_outcome` is `false`. Verify it passes.
- [x] 2.5 Run `task schema` and commit the regenerated `frontend/openapi.yaml` and `frontend/src/api/schema.d.ts`. Do not hand-edit them. Verify the diff adds only the new field.

## 3. Frontend

- [x] 3.1 Add `can_record_outcome: true` to the detail fixture in `follow-up-detail.fixtures.tsx`, and to the inline details in `follow-up-detail-page.test.tsx` and `follow-ups-page.test.tsx`. Verify existing follow-up component tests still pass.
- [x] 3.2 In `ContactSection` (`follow-up-outcome.tsx`), when `can_record_outcome` is false and the outcome is `pending` or `contacted`, render "Only an owner, the report's assignee, or its submitter can record customer contact." as muted small text in place of `RecordOutcomeForm`. Keep the owner correction branch unchanged.
- [x] 3.3 Add component tests in `follow-up-outcome.test.tsx`: with `can_record_outcome: false` on a pending follow-up, the "Record outcome" control is absent and the line is shown; on a confirmed follow-up, neither form nor line is shown; with `true`, the form shows as before. Verify they pass with `npm test` from `frontend`.
- [x] 3.4 Add a component test where submitting returns a 409 whose `current` has `can_record_outcome: false`, and the form is replaced by the line. Verify it passes.
- [x] 3.5 Take after screenshots as the brief describes and build `.switchyard/shots/compare.html`.

## 4. Repository checks

- [x] 4.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 4.2 Run `task check test build schema-check` with PostgreSQL and Redis running and verify all pass.
- [x] 4.3 Run `RESCRIBO_E2E_API_PORT=8183 RESCRIBO_E2E_FRONTEND_PORT=5183 task e2e` and verify it passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
