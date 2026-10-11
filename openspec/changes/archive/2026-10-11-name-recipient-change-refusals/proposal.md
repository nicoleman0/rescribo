# Proposal

Delivers GitHub issue #157 (milestone G. Manual check findings). Found by the manual end-to-end check (#57).

## Why

An owner picks a member under Recipient and the change is refused with "This action is no longer available for the report. The latest version is shown." The owner cannot tell what to do next. The picker offered that member, although the text above it says recipients need a Slack link.

`change_recipient` raises the same `invalid_transition` for three causes: the actor is not an owner, the new recipient has no Slack link, and the new recipient is already the recipient. A fourth refusal, a member who is no longer active, answers 404, which the form shows as "This report no longer exists, or it belongs to another workspace."

Reproduced on this branch against the demo data: a member with no Slack link is refused with 409 `invalid_transition` in every contact state (`pending`, `confirmed`, `no_response`, `still_affected`). A linked member is accepted in every one of them. The refusal in the issue came from the missing Slack link, not from the completed follow-up.

## What Changes

- A recipient change that names a member with no Slack link is refused with its own reason, `recipient_not_linked`, and a sentence that says what to do.
- A recipient change that names the current recipient is refused as `no_changes`.
- A recipient change that names a member who is not active in the workspace is refused as an invalid choice on the recipient field. **BREAKING** for API clients: 400 `invalid_reference` replaces 404.
- **BREAKING** for API clients: the two refusals above no longer answer 409 `invalid_transition`.
- The member directory says whether each member has a Slack link.
- The recipient picker lists every active member. A member with no Slack link is shown as unavailable, with the reason in the option text.
- The spec gains the recipient change rules. It had none.

Not changed: who may change a recipient, which follow-up states allow it, and the text `ActionError` shows to reports and problems.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `follow-ups`: adds requirements for changing the recipient, for refusals that name their cause, and for a picker that shows who is eligible.

## Impact

- `backend/feedback/errors.py`: one new error.
- `backend/feedback/follow_ups.py`: `change_recipient`, `has_slack_identity`, and one shared definition of a member's Slack link.
- `backend/feedback/http.py`: one branch for the new error.
- `backend/feedback/serializers.py`, `backend/feedback/views.py`: the member directory payload and the recipient endpoint's documented responses.
- `backend/tests/test_follow_ups.py`, `backend/tests/test_feedback_api.py`.
- `frontend/openapi.yaml` and the generated TypeScript contract (`task schema`).
- `frontend/src/api/reports.ts`: the type `listMembers` returns.
- `frontend/src/features/follow-ups/follow-up-detail.tsx` (`RecipientForm` only) and its tests, `frontend/e2e/follow-ups.spec.ts`.
- `frontend/DESIGN.md`: one line under "Follow-up page".
- `frontend/src/components/states/action-error.tsx` does not change.
- No migration.
