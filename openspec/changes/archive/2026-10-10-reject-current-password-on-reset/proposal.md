# Proposal

Delivers GitHub issue #142 (milestone G. Manual check findings). Found by the manual end-to-end check (#57).

## Why

A reset link accepts the password the account already has. The link is spent and sessions end, but the password that prompted the reset stays in place. The accounts spec asks only for "a valid password", and `redeem_password_reset` runs Django's validators, none of which compares with the current password.

## What Changes

- Redeeming a reset link with the account's current password is refused. This covers owner-issued and operator-issued links, which share `redeem_password_reset`.
- The refusal answers 400 with a new reason `password_unchanged`, detail "Choose a different password.", and the field error "This is your current password." under `password`.
- A refusal does not spend the link, change the password, or end sessions. The same link then works with a different password.
- Submissions to a reset link count against the account's login attempt limit, because the refusal now confirms a guess at the current password.

Unchanged: weak passwords keep `password_rejected` and "Choose a stronger password."; the request and response shape, so `frontend/openapi.yaml` stays as it is; the reset page; `operator_set_owner_password` and the `issue_owner_recovery --set-password` command; invitation acceptance.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `accounts`: adds the requirement "Password reset requires a different password". No existing requirement or scenario is reworded.

## Impact

- `backend/accounts/services.py`: one check in `redeem_password_reset`, and a lookup the throttle uses.
- `backend/accounts/views.py`: the `password_unchanged` reply in `error_response`, and a second throttle on `PasswordResetRedeemView`.
- `backend/accounts/throttling.py`: an identity-keyed throttle for the redeem endpoint.
- `backend/tests/test_accounts_password_reset.py`: new. The redeem endpoint has no API test today.
- `frontend/src/pages/token-preview-pages.test.tsx`: one added test. No page code changes.
- `openspec/specs/accounts/spec.md`: one added requirement, on archive.
- No migration, no settings change, no schema change, no screenshots.
