# Proposal

Delivers GitHub issue #144, "Check GitHub status" gives no confirmation when the check succeeds.

## Why

An owner who presses "Check GitHub status" or "Check Slack status" in Settings gets no result when the check passes. The button is disabled during the request and then returns to normal. The "Connected" badge was already showing, and "Last API success" shows minutes only, so two checks in the same minute look the same.

No existing requirement covers a result for the check. "Integration status cards" (`web-interface`) and "Connection health" (`external-operations`) describe the standing state of a connection, not the outcome of a check the owner ran.

## What Changes

- After a check passes, the card shows a result beside the check button: the connection is working, and the time of the check to the second. Slack and GitHub both get it.
- The result is announced to screen readers without moving focus.
- While the check runs, the same place reads "Checking Slack…" or "Checking GitHub…".
- A failed check shows its reason and time in that same place. It no longer appears in the "Connection update failed" box at the bottom of the card, which stays for channel actions.
- A passed result and a failed result never show together. A passed result is hidden once the connection is no longer active.
- No backend, API, or migration change. The refresh endpoint already answers 204 on a pass and 400 or 409 with a reason on a failure.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `web-interface`: adds a requirement for the result of a connection check in Settings.

## Impact

- Frontend: `frontend/src/features/settings/connection-settings.tsx` only.
- Tests: `frontend/src/features/settings/settings-page.test.tsx` and one mocked case in `frontend/e2e/settings.spec.ts`.
- Shared file, needs coordinator approval: one bullet in `frontend/DESIGN.md` under "Follow-ups and settings".
- Not touched: the `min-h-11` button sizes in this file (#156), field errors (#146), the channel picker (#148).
