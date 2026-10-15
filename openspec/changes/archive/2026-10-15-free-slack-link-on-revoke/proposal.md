# Proposal

## Why

Delivers #191. Revoking a member leaves their Slack link in place. Slack then treats the Slack user as unlinked and asks for a code, but redeeming any code fails with "This Slack account is already linked to another member." The person is told to link and cannot.

## What Changes

- Revoking a member removes that member's Slack link in the same transaction as the revocation.
- The Slack user can then link to another active member with a new code.
- Restoring a revoked member does not bring the link back. The member links again.
- A data migration removes Slack links that already point at revoked members.
- A Slack user linked to an active member is still refused when redeeming another member's code.
- Follow-up approval for a revoked recipient keeps saying to reassign the follow-up, not that the recipient has no Slack link.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `slack-connection`: adds a requirement that a Slack link ends when the linked membership is revoked.
- `accounts`: clarifies that revocation also removes a member's Slack identity.

## Impact

- `backend/connections/slack_identity.py`: a use case that revokes a membership and removes its Slack link together.
- `backend/accounts/views.py`: `MembershipRevokeView` calls that use case instead of `revoke_membership`.
- `backend/feedback/follow_ups.py`: `approve_notification` checks the recipient is active before it checks the Slack link.
- `backend/connections/migrations/0004_*`: data migration.
- No API contract change. No frontend change.
