# Design

## Context

- `_workspace_problems` in `backend/feedback/problem_reads.py` annotates `report_count`. Both `ProblemListItemSerializer` and `ProblemDetailSerializer` return it with `state`. The frontend has all the data it needs.
- `ProblemList` in `problems-page.tsx` shows the count as mono text under the row ("0 reports"). `ProblemHeader` in `problem-detail-page.tsx` shows it beside the state badge. `LinkedReports` already says "No reports are linked. The problem and its history are kept. Link a report from the Inbox."
- `problem-picker.tsx` shows the same count for each choice. Its only caller is the Link and Move form in `frontend/src/features/inbox/report-actions.tsx`.
- Ungroup and Move leave the old problem untouched apart from activity (`backend/tests/test_feedback_triage.py`, `test_moves_and_ungrouping_stay_on_both_problem_timelines`).
- There is no way to change a problem's state in the app. `change_problem_state` in `backend/feedback/problems.py` handles `start`, `decline`, and `reopen`, but no view or URL calls it. Only `backend/feedback/demo.py` and tests do. The frontend has no control for it. The `problems` spec already says members may decline a problem with a reason.

## Goals / Non-Goals

**Goals:**
- An empty problem that still counts as live work is visible at a glance in the list and on its page.
- One place holds the rule for when a problem counts as empty.

**Non-Goals:**
- A state change control, a list filter, or a prompt after Move or Ungroup.
- The next-step banner. For an empty open problem it still reads "Confirm the fix when it ships". Changing it belongs with the action it would offer.
- The demo seed. It has no empty problem and this change does not add one.

## Decisions

### D1. One component owns the rule
`NoReportsBadge` in `problem-state.tsx` takes `Pick<ProblemListItem, 'state' | 'report_count'>` and renders nothing unless the state is `open` or `in_progress` and the count is zero. The list and the header both render it without their own condition.
- Alternative: an `isEmptyProblem` helper in `problem-format.ts` plus a condition at each call site. Two call sites would each repeat the check. Add the helper only when something other than the badge needs the rule.
- `FixCard` tests the same two states for a different rule (which states can confirm a fix). They are not shared.

### D2. Warning tone
`frontend/DESIGN.md` defines warning as "needs a person's attention", which is the maintainer's decision: the owner decides. It uses `StatusBadge`, so the label is always shown and colour is not the only signal.
- Alternative: neutral. That tone means finished or inert, which is how the row reads today.

### D3. Keep the count text
The row and the header keep "0 reports". The count is a fact on every problem; the badge is the mark on some of them. Hiding the count only when the badge shows would make rows differ in shape.

### D4. Badge position
Directly after `ProblemStateBadge` in both places, so it reads "Open, No reports". On phones the list badges already wrap under the title (`frontend/DESIGN.md`, Problems list).

### D5. Picker unchanged
No badge in the picker and no change to its rows. There the count is information for choosing a target, and linking to an empty problem is a valid outcome. A new `problem-picker.test.tsx` pins that an empty problem can be chosen.

### D6. No backend code and no e2e edit
- No serializer field, query parameter, or migration. One API test pins the `problems` requirement at the list and detail endpoints.
- `frontend/e2e/report-triage.spec.ts` already reaches an empty problem and asserts "No reports are linked.", which this change keeps. The file is shared and #161 is changing the Ungroup flow it drives, so this change does not edit it. Vitest covers the list, the header, and the picker.

## Risks / Trade-offs

- [The mark has no action behind it. The only way to clear it is to link a report] → See Open Questions 1. The mark still answers the finding's "nothing marks it as empty".
- [A row can carry two warning badges, Needs review and No reports] → Both need a person. Accepted.
- [The list refreshes every 30 seconds, so the mark can lag a move made in another tab] → Same as every other value on the row.

## Decisions from planning

1. This change adds the mark only. No "Not planned" action exists yet; issue #181 covers the API and control for problem state changes, including the offer on empty problems.
2. Only `open` and `in_progress` problems get the mark.
3. There is no list filter for empty problems. The mark is enough.
