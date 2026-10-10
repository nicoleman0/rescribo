# Design

## Context

See proposal.md for the motivation. [ADR 0001](../../../docs/adr/0001-accounts-tokens-and-sessions.md) covers tokens and `session_generation`; nothing in it changes.

What the code does today, checked with a throwaway API probe on commit b26db6e:

- `accept_invitation` never reads `password` or `full_name` when the invited email has an account. It only compares the session's user with the invited account.
- Every refusal from the accept endpoint is a 400. The endpoint's OpenAPI entry already declares 401 and 429.
- The accept endpoint has `TokenRedemptionThrottle` only: 20 per hour per address (`token_redemption`). Login has `login_identity` at 10 per minute per email and `login_address` at 30 per minute.
- `preview_invitation` answers `requires_sign_in` for any existing account, with the workspace name.
- No backend test posts to the accept endpoint. Only two browser tests cover it, both for a new account.

## Goals / Non-Goals

**Goals:**

- A removed member accepts a new invitation with their existing password.
- The accept endpoint gives no more password guesses for an account than login already does.

**Non-Goals:**

- No change to the login rule or to the login error text for a non-member.
- No session for a non-member before the invitation is accepted.
- No change to #142 (password reset accepts the current password).
- No rename of the `requires_sign_in` preview status. The name is now loose, but renaming it changes the contract for no behaviour.

## Decisions

### 1. One rule for an existing account

In `accept_invitation`, when the invited email has an account:

- Session as that account: accept. No password is read. Unchanged.
- Session as another account: `sign_in_required`. The password is not read, so a second account's password cannot be tried from inside a session. Unchanged.
- No session: accept only if the account is active and `check_password` passes. Otherwise `invalid_credentials`.

The token is checked first, as today, so only a valid, unused invitation reaches the password check. A refusal raises inside the transaction, so the invitation row is not written.

The same `password` field carries the new account's password and the existing account's current password. The request shape does not change. Alternative: a separate `current_password` field. Rejected: it changes the contract and the two uses never meet in one request.

### 2. Wrong password answers 401 `invalid_credentials`

Reply: status 401, `reason: invalid_credentials`, `detail: "Password is incorrect."`, `field_errors: {"password": ["Password is incorrect."]}`.

- 401 and the reason match what login returns for the same failure. The endpoint already declares 401, so `frontend/openapi.yaml` does not change.
- The detail names the password because the invitation fixes the email. The preview already tells the link holder that the account exists.
- A blank or missing password and a deactivated account get the same reply.
- The page shows the text under the password field through `Field`'s inline error, per `frontend/DESIGN.md`.

Alternative: 400 like the endpoint's other refusals. Rejected: the client would need the reason to tell a credential failure from a dead link, where login already uses 401.

### 3. Password attempts share the login identity limit

`InvitationPasswordThrottle` joins `TokenRedemptionThrottle` on `InviteAcceptView`. It resolves the token to the invited email and uses the same cache key as `LoginIdentityThrottle`, so accept and login draw on one budget per account: 10 per minute (`login_identity`). It skips a request that has a session or whose invitation creates a new account, because neither checks a password.

Why the address limit alone is not enough: any workspace owner can mint an invitation for any email, so holding the link is not a barrier. 20 per hour per address is tighter than login from one address, but from more than 30 addresses it would allow more guesses per account than login's 600 per hour. Sharing the bucket makes the accept endpoint no weaker than login.

- No settings change: the scope `login_identity` already has a rate.
- A link holder can use up the victim's login budget. Anyone can already do that on the login endpoint by posting the email.
- Alternative: key on the token. Rejected: an owner rotates the token by inviting again.
- Alternative: revoke the invitation after N wrong passwords. Rejected: a wrong password must not consume the invitation.

### 4. An account active in another workspace may also use its password

Today such an account is refused without a session and accepted with one. After the change it is also accepted without a session when the password matches. This is the same proof of identity as signing in first, under the same identity limit, and it keeps one page state for every existing account.

The alternative keeps the password path for accounts with no active membership only. It needs either a second preview status, which tells a link holder whether the account is active in some other workspace, or a password form that can answer "sign in instead". See question 1 in the plan summary.

### 5. Page

For `requires_sign_in` with no session, `accept-invite-page.tsx` shows a form in place of the "Sign in to accept" link:

- Text: "Join {workspace}. This email already has an account. Enter its password to accept."
- One `Field`: label "Password", `autoComplete="current-password"`.
- Button: "Accept invitation".
- A wrong password shows "Password is incorrect." under the field and keeps the typed value. Any other error (throttled, dead link) shows as the page's existing alert line.

A request signed in as another account is still refused with `sign_in_required`. Its detail text changes from "The request could not be completed." to "This invitation is for a different account. Sign out, then open the link again.", because signing out now leads to the password form. See question 3 in the plan summary.

The signed-in confirmation state, the new-account form, and the expired state do not change. The accept call stays in the page; no file under `frontend/src/api/` changes.

### 6. Session binding needs no change

`revoke_membership` raises `session_generation` when the last active membership goes. `accept_invitation` loads the user inside its transaction, so the view binds the raised value and the new session authenticates. Sessions from before the removal hold the old value and stay dead. A browser that still carries the old cookie is logged out by `SessionGenerationMiddleware` before the view runs, so it takes the password path. The API test and the browser test both assert this.

### 7. Refusals, before and after

| Case | Today | After |
| --- | --- | --- |
| Removed member, no session, right password | 400 `sign_in_required` (the bug) | 200, signed in |
| No session, wrong, blank, or missing password | 400 `sign_in_required` | 401 `invalid_credentials`, no session, invitation usable |
| Session as another account (invitation issued to a different email), with or without the invited account's password | 400 `sign_in_required` | 400 `sign_in_required`, clearer detail text |
| Account active in another workspace, session as it | 200 | 200 |
| Account active in another workspace, no session, right password | 400 `sign_in_required` | 200 (decision 4) |
| Account active in another workspace, no session, wrong password | 400 `sign_in_required` | 401 `invalid_credentials` |
| Deactivated account, right password | 400 `sign_in_required` (it cannot hold a session) | 401 `invalid_credentials` |
| Expired, used, revoked, or unknown token | 400 token reason | 400 token reason, checked before the password |
| Login for an account with no active membership | 401 `invalid_credentials` | 401 `invalid_credentials` |

### 8. Tests isolate the throttle cache

Throttle counts live in the Redis cache and survive between tests and runs. The new API test file swaps `CACHES` to a per-test `LocMemCache` with the `settings` fixture, so each test has its own budget and nothing is written to Redis. It does not call `cache.clear()`, which would flush the whole Redis index.

The browser tests share one address. This change adds three token redemptions per run, six in total against 20 per hour, so a fourth full run inside an hour gets 429. tasks.md gives the command that clears that one key in the worktree's Redis index.

### 9. Screenshots

`shots.mjs` signs in as the demo visitor and does not open the invitation page. The planner added two git-ignored helpers in `.claude/shots/`: `invite-fixture.py` builds a removed member with a pending invitation, and `invite-shots.mjs` captures the page signed out for an existing account and for a new one, in light and dark at both widths. Before shots are in `.claude/shots/before/`. The shared `shots.mjs` is not edited.

## Risks / Trade-offs

- [The accept endpoint now checks passwords] → The shared identity limit and the existing address limit bound it. A test drives the limit to 429 on both endpoints.
- [`check_password` runs while the invitation row is locked] → One hash check, about as long as a login. Only requests for the same invitation wait.
- [`identity_key` is extracted from `LoginIdentityThrottle` in the same change] → The login key is unchanged; the login-limit test would fail if it moved.
