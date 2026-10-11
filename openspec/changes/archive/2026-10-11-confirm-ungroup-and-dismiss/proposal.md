# Proposal

Delivers GitHub issue #161, "[Check] Ungroup and Dismiss act at once with no confirmation or undo prompt".

## Why

In the report triage section, Ungroup and Dismiss apply on the first click. Ungroup also cancels any unsent employee notification for the report, so a slip has a side effect that linking again does not undo. Dismiss is styled as destructive but does not ask.

The maintainer decided on a confirm step for both actions, every time. Not an undo notice, and not only when a notification would be cancelled.

No existing requirement covers this. `problems` and `reports` describe what ungroup and dismiss do on the server, which does not change.

## What Changes

- Ungroup and Dismiss each open a confirm step in place of the triage actions. Nothing is sent until the member confirms.
- The Ungroup step says the report returns to New, that any unsent employee notification for it is cancelled, and that sent history is kept. The Dismiss step says the report is kept, is not grouped or followed up, and can be restored.
- Cancel changes nothing and returns focus to the button that opened the step.
- A failed attempt keeps the step open with the reason. If the report changed so the action no longer applies, the step closes and no other action is applied in its place.
- The step works by keyboard alone and keeps 44px targets on phones.
- The box, text, and button row of the settings typed-phrase confirm move into one shared component. Settings keeps its typed phrase and looks and behaves as it does today.
- Restore report, Move to problem, Move to new problem, and Save assignee are unchanged.
- No backend, API, or migration change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `web-interface`: adds a requirement that Ungroup and Dismiss ask before they change a report.

## Impact

- Frontend: `frontend/src/features/inbox/report-actions.tsx`, and a new shared `frontend/src/components/confirm/confirm-panel.tsx`.
- Not on the owned list, needs coordinator approval: `frontend/src/features/settings/confirm-action.tsx` renders the shared component instead of its own box. No behaviour change.
- Tests: `frontend/src/features/inbox/report-actions.test.tsx`, a new `frontend/src/components/confirm/confirm-panel.test.tsx`, and `frontend/e2e/report-triage.spec.ts`. Settings tests stay as they are and must pass unchanged.
- Shared file, additions only: two bullets in `frontend/DESIGN.md`.
- Not touched: `frontend/src/features/problems/` (#162), `frontend/src/components/forms/` (#146), the UI gallery.
