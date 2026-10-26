# Proposal

Delivers GitHub issue #242.

## Why

#182 added `signIn(page, credentials)` in `frontend/e2e/session.ts`, but six specs still fill the sign-in form inline or in a private wrapper. The sign-in steps and the login throttle workaround should live in one place. Sign-ins that test the form itself stay inline.

## What Changes

- `seed-session.ts`: the `Seed` type gains `expired_invitation_token`, so `accounts.spec.ts` can use `readSeed()`.
- `accounts.spec.ts`: 3 setup sign-ins move to `readSeed()` and `signIn`. 4 stay inline because they test the sign-in form. The local `seedPath`, `Seed`, and file reads go.
- `settings.spec.ts`: 4 sign-ins move to `readSeed()` and `signIn`. The local `authDir` and file reads go.
- `seed-session.ts`: add `signInAsSeededOwner(page)`, built on `readSeed()` and shared `signIn(page, seed.users[2])`. Keep the fixed-credentials rationale there once.
- `inbox.spec.ts`, `fix-release.spec.ts`, `github-issues.spec.ts`: call `signInAsSeededOwner` directly. Inbox keeps its title check after the helper call. Remove each private wrapper and local seed reads.
- `ui-foundation.spec.ts`: the 'user menu signs out' sign-in moves to `readSeed()` and `signIn`. The local `authDir`, `seedPath`, and file read go.
- Every test and assertion stays, in order, with the same user.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Test tooling only, so `skip_specs: true`.

## Impact

- Files: `frontend/e2e/seed-session.ts`, `accounts.spec.ts`, `settings.spec.ts`, `inbox.spec.ts`, `fix-release.spec.ts`, `github-issues.spec.ts`, `ui-foundation.spec.ts`.
- Out of scope: `follow-ups.spec.ts` (#237) and `motion.spec.ts` (#239). `demo.spec.ts` drives the demo login button on the form, so it stays as is.
- No app code, API, or dependency changes.
