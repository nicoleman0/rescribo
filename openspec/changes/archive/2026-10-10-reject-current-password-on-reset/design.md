# Design

## Context

See proposal.md for the motivation. [ADR 0001](../../../docs/adr/0001-accounts-tokens-and-sessions.md) covers tokens and `session_generation`; nothing in it changes.

What the code does today, on commit 65232e7:

- `redeem_password_reset` checks the token and eligibility, runs `validate_password`, then sets the password, raises `session_generation`, and spends the link. A validator failure raises `TokenError("password_rejected")` before any write.
- `error_response` answers `password_rejected` with 400, detail "Choose a stronger password.", and the validator messages under `field_errors.password`.
- The reset page shows `field_errors.password[0]` under the "New password" field and the detail as a second line below the form. It does not read `reason`.
- `PasswordResetRedeemView` has `TokenRedemptionThrottle` only: 20 per hour per address. Login has `login_identity` at 10 per minute per email.
- The only password-setting paths are reset links, invitations, and the operator command. There is no ordinary password change flow.
- No backend test posts to the redeem endpoint.

The code blocks in tasks.md were run against a throwaway prototype on 65232e7 and then reverted.

## Goals / Non-Goals

**Goals:**

- A reset link cannot leave the current password in place.
- The redeem endpoint gives no more guesses at an account's password than login does.

**Non-Goals:**

- No password change screen or endpoint.
- No password history. Only the current password is compared.
- No change to the reset page, the request or response shape, or weak-password wording.
- No change to `operator_set_owner_password`. See question 3 in the plan summary.

## Decisions

### 1. The check sits on the existing refusal path

In `redeem_password_reset`, after `validate_password` and before `set_password`:

```python
if check_password(password, reset.user.password):
    raise TokenError("password_unchanged")
```

- It raises before any write, inside the transaction, so the link, the password, and `session_generation` are untouched. This is the same position as `password_rejected`.
- It uses `django.contrib.auth.hashers.check_password`, not `user.check_password`. The user method rewrites the stored hash when the hasher settings have changed, and a refusal should write nothing.
- An account with an unusable password never matches, so its reset proceeds.
- Validators run first. A current password that no longer passes them is refused as `password_rejected`.

Alternative: a custom validator in `AUTH_PASSWORD_VALIDATORS`. Rejected: it lives in shared settings, and it would also apply to the operator command, which stays unchanged.

### 2. A new reason, `password_unchanged`

Reply: status 400, `reason: password_unchanged`, `detail: "Choose a different password."`, `field_errors: {"password": ["This is your current password."]}`.

- The page shows the field error under "New password" and the detail below the form. The two lines read as cause, then action, and do not repeat each other.
- `error_response` owns both strings, as it does for `invalid_credentials`. The service raises only the reason.
- `password_rejected` and "Choose a stronger password." stay for validator failures, so invitation acceptance and the operator command are untouched.
- `reason` is a plain string in `ErrorSerializer`, and the endpoint already declares 400. `task schema-check` reported no change on the prototype.

Alternative: reuse `password_rejected` and make its detail neutral for every refusal. Rejected: it rewords the invitation page for a change that is about resets. See question 1 in the plan summary.

### 3. Submissions share the login identity limit

Before this change the redeem endpoint said nothing about the current password. After it, `password_unchanged` confirms a guess, and a refusal leaves no trace for the account holder: the link is unspent and sessions stay valid. A link is also seen by the owner who issued it in Settings, or by the operator who ran the command.

`PasswordResetPasswordThrottle` joins `TokenRedemptionThrottle` on `PasswordResetRedeemView`. It resolves the token to the account's email and uses the same cache key as `LoginIdentityThrottle`, so redeem and login draw on one budget per account: 10 per minute. This follows `InvitationPasswordThrottle` from #143.

- The address limit alone allows 20 guesses per hour per address. From more than 30 addresses that exceeds login's 600 per hour for one account.
- Every submission to a known link counts, including weak passwords and dead links. Counting only live links would repeat the validity check in the throttle.
- A link holder can use up the account's login budget. Anyone can already do that on the login endpoint with the email.
- No settings change: the scope `login_identity` already has a rate.
- An unknown token has no account, so only the address limit applies.

Alternative: keep the address limit only. Smaller, but weaker than login under many addresses. See question 2 in the plan summary.

### 4. Tests

- `backend/tests/test_accounts_password_reset.py` posts to the redeem endpoint. It asserts the exact reply, that the link, password, and `session_generation` are unchanged, that an existing session still authenticates, and that the same link then works.
- The file swaps `CACHES` to a per-test `LocMemCache`, as `test_accounts_invitation_accept.py` does, so throttle counts never reach Redis. The eight-line fixture is copied. Sharing it means moving it to `backend/tests/conftest.py`, a shared file; flagged in the plan summary.
- One page test in `frontend/src/pages/token-preview-pages.test.tsx` covers what the reset page shows for a refusal. No test covers that path today. It passes without any page change. See question 4 in the plan summary.
- No browser test is added. The existing reset test in `frontend/e2e/accounts.spec.ts` still passes, because `seed_test_accounts` resets the member's password on every run and the test sets a different one.

## Risks / Trade-offs

- A reset link becomes a yes or no check on the current password. Decision 3 holds its rate to the login rate. The holder of a valid link can already take over the account.
- Each accepted submission costs one extra password hash. The endpoint is throttled.
- Playwright has no retries configured. If retries are added later, a retry of the existing reset test after a successful redeem would submit the then-current password and be refused.
