# Proposal

Delivers GitHub issue #182.

## Why

`follow-ups.spec.ts` and `report-triage.spec.ts` each keep a private copy of the sign-in-once-and-save-`storageState` code that `seed-session.ts` already provides. `demo-session.ts` repeats the same sign-in steps for the demo user. The login throttle workaround should live in one place.

## What Changes

- Add `frontend/e2e/session.ts` with the shared core: the `.auth` directory, `signIn(page, credentials)`, and `saveSession(browser, baseURL, sessionPath, credentials)`.
- `seed-session.ts` keeps `seedSessionPath` and `saveSeedSession`, built on the core, and exports `readSeed()`.
- `demo-session.ts` keeps its exports and signatures, built on the core.
- `follow-ups.spec.ts` (user 5) and `report-triage.spec.ts` (user 4) call `saveSeedSession` and drop their local `saveSession`, `authDir`, `seedPath`, and `Seed`.
- The two other sign-ins in `follow-ups.spec.ts` (the owner fallback in `ensureFollowUpOwner` and the member at user 7) use `readSeed()` and `signIn`.
- Every test and assertion in both specs stays, in order.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Test tooling only, so `skip_specs: true`.

## Impact

- Files: `frontend/e2e/session.ts` (new), `seed-session.ts`, `demo-session.ts`, `follow-ups.spec.ts`, `report-triage.spec.ts`.
- Specs that import `seed-session.ts` or `demo-session.ts` keep their calls unchanged: `command-palette`, `theme-tokens`, `settings`, `ui-foundation`, `z-product-states`, `demo`, `motion`, `themes`.
- Session files move from `.auth/follow-ups-owner.json` and `.auth/triage-owner.json` to `.auth/seed-follow-ups-owner.json` and `.auth/seed-triage-owner.json`. `.auth/` is git-ignored and rewritten each run.
- No app code, API, or dependency changes.
