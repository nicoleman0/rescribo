# Proposal

## Why

Delivers GitHub issue #237. An owner can change a follow-up's recipient. The new recipient can record the customer outcome from the Slack DM, but the web app allows only an owner, the report's assignee, or its submitter. A reassigned recipient who is none of those sees the "Only an owner..." line in place of the form, and a direct request gets a 409. The two paths disagree about the same person.

## What Changes

- In the web app, the follow-up's current recipient may also record a customer contact outcome. The rule becomes: an owner, the report's assignee, the report's submitter, or the follow-up's recipient.
- The follow-up detail's `can_record_outcome` follows the new rule, because it uses the same rule as the outcome endpoint.
- A member who stops being the recipient loses the right, unless another clause still grants it.
- The line shown in place of the form names the recipient too.
- No change to Slack: only the linked recipient records there. No change to owner corrections or to who may change the recipient.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `follow-ups`: "Who records outcomes" and "Contact form follows recording permission" add the follow-up's recipient to the web app rule and to the line shown in place of the form.

## Impact

- Backend: `backend/feedback/follow_ups.py` (`can_record_outcome` takes the follow-up as well as the report), `backend/feedback/serializers.py` (`FollowUpDetailSerializer.get_can_record_outcome`).
- API: no shape change. `can_record_outcome` returns `true` for more members. No schema regeneration.
- Frontend: the line text in `frontend/src/features/follow-ups/follow-up-outcome.tsx` and its test.
- Tests: `backend/tests/test_follow_ups.py`, `frontend/src/features/follow-ups/follow-up-outcome.test.tsx`.
