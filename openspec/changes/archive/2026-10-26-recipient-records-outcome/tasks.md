# Tasks

## 1. Backend rule

- [x] 1.1 Change `can_record_outcome` in `backend/feedback/follow_ups.py` to `(*, actor, follow_up, report)`. Assert `follow_up.report_id == report.pk`. Add the clause `follow_up.recipient_id == actor.pk`. Update its docstring and the `record_outcome` docstring ("Recording: ...") to name the recipient. Leave the Slack branch alone.
- [x] 1.2 Update both callers: `record_outcome` passes the locked `follow_up` and `report`; `FollowUpDetailSerializer.get_can_record_outcome` passes `follow_up` and `follow_up.report`. Verify with `grep -rn "can_record_outcome(" backend/feedback` that no caller uses the old signature.
- [x] 1.3 In `backend/tests/test_follow_ups.py`, add a service test: an owner changes the recipient to a linked member who is not owner, assignee, or submitter; that member records `contacted` and `outcome_by` is that member. Add a test that after a second change away from that member, they get `InvalidTransition` and `contact_state` is unchanged. Verify both pass.
- [x] 1.4 Extend the API tests: `GET follow-ups/<id>/` returns `can_record_outcome: true` for the reassigned recipient and `false` for the former recipient after a further change; `POST .../outcome/` from the reassigned recipient returns 200. Verify they pass.
- [x] 1.5 Add a cross-workspace test: the same user's membership in another workspace gets 404 on `GET` and `POST .../outcome/` for the follow-up, and nothing changes. Verify it passes.
- [x] 1.6 Run `uv run pytest backend/tests/test_follow_ups.py backend/tests/test_slack_outcomes.py` and verify the existing tests, including the parametrized `test_detail_says_whether_the_viewer_may_record` and the Slack reassignment test, pass unchanged.

## 2. Frontend line

- [x] 2.1 In `frontend/src/features/follow-ups/follow-up-outcome.tsx`, change the line to "Only an owner, the report's assignee or submitter, or the follow-up's recipient can record customer contact." Update the constant in `follow-up-outcome.test.tsx`. Verify with `npm test` from `frontend`.

## 3. Repository checks

- [x] 3.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 3.2 Run `task check test build schema-check` with PostgreSQL and Redis running and verify all pass. `schema-check` must show no diff: the API shape does not change.
- [x] 3.3 Run `RESCRIBO_E2E_API_PORT=8237 RESCRIBO_E2E_FRONTEND_PORT=5237 task e2e` and verify it passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
