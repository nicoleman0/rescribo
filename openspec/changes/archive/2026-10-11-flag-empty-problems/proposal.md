# Proposal

Delivers GitHub issue #162, A problem with no reports is left behind when its last report moves (milestone G. Manual check findings).

## Why

When a member moves or ungroups the only report of a problem, the problem stays in the list as Open with "0 reports" in small text. Nothing marks it, so empty problems collect and look like live work.

The maintainer decided: flag the empty problem and let the owner decide. No automatic state change and no deletion. History is kept.

## What Changes

- The problems list and the problem detail header show a "No reports" status on an `open` or `in_progress` problem with no linked reports.
- Problems that are `fix_available` or `not_planned` never show it. They are already settled.
- The mark goes away when a report is linked to the problem again.
- The problem picker is unchanged. An empty problem stays selectable there, so a report can be linked to it again.
- The spec records the rule that an empty problem keeps its state and history.

Not in this change:

- No list filter for empty problems.
- No offer to mark the problem Not planned. The app has no such action today: `change_problem_state` has no endpoint and no control. See design.md, Open Questions.
- No prompt after Move or Ungroup (#161 owns `report-actions.tsx`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `problems`: adds a requirement that a problem left without reports keeps its state and history.
- `web-interface`: adds a requirement for the "No reports" mark in the problems list and on problem detail.

## Impact

- Frontend only: `problem-state.tsx`, `problems-page.tsx`, `problem-detail-page.tsx` in `frontend/src/features/problems/`, with their tests and a new `problem-picker.test.tsx`.
- `frontend/DESIGN.md`: one bullet appended to "Problems list".
- Backend: no code change. `report_count` is already on the list and detail serializers. One API test is added in `backend/tests/test_feedback_triage_api.py`.
- No API contract change, no `task schema` output, no migration.
