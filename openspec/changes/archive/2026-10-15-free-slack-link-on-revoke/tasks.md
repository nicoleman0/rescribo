# Tasks

## 1. Revoke removes the Slack link

- [x] 1.1 Add `revoke_member(*, actor, target)` to `backend/connections/slack_identity.py`: inside `transaction.atomic()`, call `accounts.services.revoke_membership(actor=actor, target=target)`, then `unlink(target)`. Leave `revoke_membership` unchanged. Verify with the tests in 1.3.
- [x] 1.2 Switch `MembershipRevokeView` in `backend/accounts/views.py` to call `revoke_member`, keeping the `LastActiveOwner` handling. Verify: `test_last_owner_revoke_is_a_400` still passes.
- [x] 1.3 Add service tests in a new `backend/tests/test_slack_link_revoke.py`:
  - revoking a linked member removes their Slack identity, and the same Slack team and user then redeem another active member's code and resolve to that member through `linked_membership`;
  - after revoking and then restoring the member through `accept_invitation`, `linked_identity` is `None`;
  - the same user has linked memberships in two workspaces; revoking one leaves the other workspace's identity unchanged;
  - revoking the last active owner raises `LastActiveOwner` and the owner's identity is still there;
  - when `unlink` raises (patched), the membership is still active and the identity is still there;
  - a Slack user linked to an active member redeeming another member's code still raises `LinkCodeRejected` with "This Slack account is already linked to another member.", and both identities are unchanged.
- [x] 1.4 Add an API test to `backend/tests/test_accounts_api.py`: an owner posts to the revoke endpoint for a linked member; the response is 204 and the member's Slack identity is gone. Add a cross-workspace case: an owner of workspace A posting a workspace B membership ID gets 404 and the B identity is unchanged.

## 2. Data migration

- [x] 2.1 Add `backend/connections/migrations/0004_free_revoked_slack_links.py`, depending on `connections.0003_slack_capture` and `accounts.0003_workspace_is_demo`. `RunPython` with historical models deletes `ExternalIdentity` rows with `provider="slack"` and `membership__is_active=False`. Reverse is `migrations.RunPython.noop`. Verify: `uv run python backend/manage.py makemigrations --check --dry-run` reports no changes.
- [x] 2.2 Test the migration in `backend/tests/test_slack_link_revoke.py` with `MigrationExecutor`: migrate to 0003, create an active linked member, a revoked linked member, and a revoked linked member in a second workspace, migrate to 0004, and assert only the active member's identity remains.

## 3. Follow-up approval reason for a revoked recipient

- [x] 3.1 In `approve_notification` in `backend/feedback/follow_ups.py`, move the active-recipient check above `slack_readiness(follow_up=follow_up)`. Do not change either check's body. Verify with 3.2.
- [x] 3.2 Add a test next to the existing approval tests: draft a notification for a linked recipient, revoke the recipient through `revoke_member`, approve, and assert `DeliveryNotReady` with reason `recipient_inactive`.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running. `schema-check` must report no contract change. Record the test counts for the PR.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8191 RESCRIBO_E2E_FRONTEND_PORT=5191 task e2e` passes, since the revoke endpoint changed. Record the counts for the PR.

## Workflow follow-up

- Archive this change in the PR that completes #191 (`/opsx:archive`).
- The PR closes #191. Milestone: G. Manual check findings.
- No screenshots: no web UI changes.
- PR body lists: where the unlink call lives and why, the migration that deletes links on revoked members, and the reordered approval check.
