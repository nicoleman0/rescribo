# Proposal

Delivers GitHub issue #143 (no milestone). Found by the manual end-to-end check (#57).

## Why

A member whose only membership was removed cannot accept a new invitation. `accept_invitation` requires an existing account to be signed in, and the login view refuses any account with no active membership. The two rules deadlock, so the only workaround is to invite the person under another email address.

The accounts spec has no scenario for an existing account accepting an invitation.

## What Changes

- The invitation page asks an existing account for its current password and accepts in one step. The maintainer chose this on 10 Oct 2026 over allowing sign-in for a user with a pending invitation.
- The accept endpoint checks that password when the request has no session. A match accepts the invitation and signs the account in.
- A wrong, blank, or missing password answers 401 `invalid_credentials`. It starts no session and leaves the invitation usable.
- Password attempts on an invitation count against the invited account's login attempt limit.
- A request signed in as the invited account still accepts without a password. A request signed in as another account is still refused, with or without the password.
- The page drops the "Sign in to accept" link, which led a removed member to a login that always failed.

Unchanged: the login rule, the request and response shape of the accept and preview endpoints, `frontend/openapi.yaml`, and the new-account path.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `accounts`: adds the requirement "Invitation acceptance by an existing account". No existing requirement or scenario is reworded.

## Impact

- `backend/accounts/services.py`: the existing-account branch of `accept_invitation`, and a lookup the throttle uses.
- `backend/accounts/throttling.py`: an identity-keyed throttle for the accept endpoint.
- `backend/accounts/views.py`: the 401 reply and the throttle on `InviteAcceptView`.
- `backend/tests/test_accounts_invitation_accept.py`: new. The accept endpoint has no API test today.
- `frontend/src/pages/accept-invite-page.tsx`, `frontend/src/pages/token-preview-pages.test.tsx`, `frontend/e2e/accounts.spec.ts`.
- `openspec/specs/accounts/spec.md`: one added requirement, on archive.
- No migration, no settings change, no shared `frontend/src/api/` file.
