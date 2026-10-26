# Design

## Context

- `session.ts` `signIn(page, credentials)`: goto `/sign-in`, fill the `Email` textbox and `Password`, click `Sign in`, expect `/inbox$`.
- `seed-session.ts` `readSeed()` returns the seed data from `.auth/seed.json`. Its shared `signInAsSeededOwner(page)` helper signs in user 2 through `signIn`.
- `seed_test_accounts` gives every seeded user the same password. `seed.users[1].email` with `seed.users[0].password` is user 1's own credentials, so `signIn(page, seed.users[1])` signs in the same user.

Inline sign-ins on this branch, recounted (the issue counts predate #182):

| Spec | Line | User | Test | Plan |
|---|---|---|---|---|
| accounts | 21 | 1 | owner signs in and signs out | keep: tests the form signs an owner in |
| accounts | 120 | 3 | a member accepts an invitation | move: setup for the invite |
| accounts | 159 | invited | same test, after sign-out | keep: tests the password set on accept |
| accounts | 171 | 0 | owner issued password reset link | move: setup for the reset |
| accounts | 211 | member | same test, after reset | keep: tests the reset password |
| accounts | 226 | 3 | removed member accepts a new invitation | move: setup for the invite |
| accounts | 299 | reinvited | same test, after sign-out | keep: tests the password after re-invite |
| settings | 179 | 1 | long member email at 320px | move |
| settings | 208 | 1 | Slack connect form passes API validation | move |
| settings | 241 | 1 | passing Slack check (mocked) | move |
| settings | 270 | 4 | owner allows and removes a Slack channel | move |
| inbox | 26 | 2 | private wrapper, `beforeEach` | move |
| fix-release | 15 | 2 | private wrapper, 1 call | move |
| github-issues | 20 | 2 | private wrapper, 2 calls | move |
| ui-foundation | 207 | 8 | user menu signs out | move: subject is sign-out |

Not counted: form-only tests in accounts (keyboard, mobile width, button size), which fill no credentials or do not submit, and `demo.spec.ts`, which submits the demo login.

## Goals / Non-Goals

**Goals:**
- Every sign-in that only needs a session goes through `signIn`.
- Same user, same tests, same assertions, same order.

**Non-Goals:**
- `follow-ups.spec.ts`, `motion.spec.ts`, `demo.spec.ts`, `auth.setup.ts`.
- Turning per-test sign-ins into saved sessions. The number of logins per identity stays as it is.
- Per-test session reuse; login counts stay the same.

## Decisions

### One shared seeded-owner helper

`signInAsSeededOwner(page)` in `seed-session.ts` uses `readSeed()` and the shared `signIn` for user 2. The inbox, fix-release, and github-issues specs share this fixed account, so its credential choice and rationale have one home. The specs call the helper directly; inbox keeps its title assertion after the call.

### Keep the four accounts sign-ins that test the form

Each one is the point of its test: the form signs a user in, or a password set on accept, reset, or re-invite works. If `signIn` changes later, for example to sign in through the API, these tests must keep driving the form. The other three accounts sign-ins are setup for an owner who then calls the API.

The three kept after `signOut` (lines 159, 211, 299) fill the form without a `goto`, because sign-out already lands on `/sign-in`. That stays.

### `Seed` gains `expired_invitation_token`

`accounts.spec.ts` reads it for the expired invitation test. Adding it to the shared type lets the spec drop its own `Seed` and `seedPath`. `seed_test_accounts --json` already writes the field.

### `settings.spec.ts` uses the Email textbox role

The inline steps used `getByLabel('Email')`; `signIn` uses `getByRole('textbox', { name: 'Email' })`. Both match the same input on `/sign-in`.

## Risks / Trade-offs

- [A moved test silently changes user] → Each call passes the same `seed.users[i]` index as before; the diff review checks this.
