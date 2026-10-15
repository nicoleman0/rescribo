# Design

## Context

- `accounts.services.revoke_membership` locks the membership, sets `is_active = False`, and ends sessions. It is the only path that deactivates a membership. Its one caller outside tests is `MembershipRevokeView`.
- `connections` imports from `accounts`, and `accounts.services` imports nothing from `connections`. `docs/DEVELOPMENT.md` gives `accounts.services` the account invariants and keeps providers out of it.
- `ExternalIdentity` belongs to one workspace and one membership. Its unique key includes the workspace, so deleting by membership never reaches another workspace.
- Restore paths (`accept_invitation`, owner bootstrap) set `is_active = True` on the old membership row. They do not touch identities.

## Goals / Non-Goals

**Goals:**
- Revocation and link removal commit or roll back together.
- `accounts.services` stays free of `connections` imports.

**Non-Goals:**
- Clearing unused link codes of the revoked member. Redemption already refuses a code whose member is inactive.
- Changing how the follow-up screen presents a revoked recipient beyond the approval check order.
- Any change to the "Link Rescribo account" shortcut beyond the new scenarios (#149).

## Decisions

### A `connections` use case wraps the revoke

Add `revoke_member(*, actor, target)` to `connections/slack_identity.py`. It opens `transaction.atomic()`, calls `accounts.services.revoke_membership`, then calls the existing `unlink(target)`. `MembershipRevokeView` calls `revoke_member` in place of `revoke_membership`; its error handling stays the same.

- The dependency keeps its direction: `connections` calls `accounts`.
- `revoke_membership` runs inside the outer transaction as a savepoint. A refusal (`LastActiveOwner`, `LookupError`) raises before `unlink`, so the link stays. A failure in `unlink` rolls the revocation back.
- `unlink` runs even when the target was already inactive. That is harmless and clears any stale link.

Alternatives:
- A `membership_revoked` Django signal sent from `revoke_membership`, with a receiver in `connections`. It enforces the rule on every caller and keeps `accounts` ignorant of Slack. Rejected for now: the repo has no signals, the control flow is hidden, and there is one caller. Worth revisiting if a second provider identity or a second revoke path appears.
- Delete through the reverse relation inside `revoke_membership`. Rejected: `accounts` would encode Slack knowledge.
- Do it in the view. Rejected: views stay thin, and the transaction belongs in a use case.

### Concurrent redemption needs no new lock

`redeem_link_code` selects the code with `select_for_update()` and `select_related("membership")`. Without `of=`, PostgreSQL locks the joined membership row too. `revoke_membership` locks the same row. So a redeem and a revoke on the same member serialize. If revoke commits first, the redeem re-checks `membership__is_active=True` after the wait and finds no code. If redeem commits first, the revoke then removes the new link.

### Data migration

`connections/migrations/0004_*` runs `RunPython` with the historical models: delete Slack `ExternalIdentity` rows whose membership has `is_active=False`. Reverse is a no-op, since the deleted links cannot be rebuilt and restore does not bring links back anyway.

### Follow-up approval checks the recipient first

`approve_notification` calls `slack_readiness` before it checks that the recipient is active. Today a revoked recipient still has a link, so approval returns `recipient_inactive` ("Reassign this follow-up to an active member"). After this change it would return `no_slack_identity` ("This member has not linked a Slack account") instead. Move the active check above `slack_readiness` so the reason stays "reassign", which matches the follow-ups spec ("If the recipient has left, an owner reassigns the report before sending"). The worker path in `slack_delivery._authorize` already checks activity before the link.

## Risks / Trade-offs

- [A new caller uses `revoke_membership` directly and skips the unlink] → The data migration covers the past only. A test asserts the revoke endpoint removes the link. The signal alternative is the fix if a second caller appears.
- [The follow-up screen shows "Copy to send to <name>" for a revoked recipient, because `has_slack_link` is now false] → Accepted. The recipient is inactive and approval already refuses; reassigning restores the right destination.
- [The migration deletes data that cannot be restored] → The links are unusable today (`linked_membership` ignores inactive members), and restore would require a fresh link under the new rule.

## Migration Plan

Deploy runs the data migration with the other migrations. Rollback leaves the deleted links deleted; the old code then simply finds no link for those revoked members.
