# Proposal

Delivers GitHub issue #160 (milestone G. Manual check findings). Found by the manual end-to-end check (#57).

## Why

An employee who already told the customer about a fix cannot record it. The follow-up detail shows the Customer contact section only after "Prepare message" creates a draft notification. The workaround is a draft nobody sends.

The `follow-ups` spec already says customer contact is "independent of delivery". The server agrees: `record_outcome` never reads the notification row, and the Slack outcome path handles a follow-up with no notification. Only the page couples the two.

The maintainer decided: contact can be recorded on a follow-up with no message draft, always. The section shows from the start. No note is required for "Customer contacted".

## What Changes

- The follow-up detail (panel and full page) always shows the Customer contact section, whatever the delivery state, including no notification and a notification cancelled by a recipient change.
- Recording an outcome leaves an unsent draft as it is (open question 1 in design).
- When an outcome is recorded and no message was prepared, the Message section keeps "Prepare message" and says contact is already recorded (open question 2 in design).
- Tests cover recording with no notification on the server, in the component, and in the browser.

No API, schema, model, or bucket change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `follow-ups`: adds the requirement "Contact without a message".

## Impact

- `frontend/src/features/follow-ups/follow-up-detail.tsx` (`FollowUpBody`, `DraftSection`).
- `frontend/src/features/follow-ups/follow-up-detail.test.tsx`, `frontend/e2e/follow-ups.spec.ts`, `backend/tests/test_follow_ups.py` (new tests).
- `openspec/specs/follow-ups/spec.md` (one added requirement).
- Not touched: `backend/feedback/follow_ups.py`, `backend/connections/slack_outcomes.py`, `frontend/openapi.yaml`.
