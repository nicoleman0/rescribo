# Proposal

## Why

Delivers #221. Two e2e tests failed in one full run and passed in the next. One matches more than the element it means. The other is a long journey that runs past Playwright's 30 second test timeout when the machine is under load.

## What Changes

- `ui-foundation.spec.ts` "shell at desktop width": match the `Follow-ups` page heading exactly, so the "No follow-ups yet" empty-state heading cannot also match.
- `settings.spec.ts` "owner manages invitations, members and confirmed deletion on desktop and mobile": split the journey into ordered tests in a serial block. Each test does one part of the journey and gets its own timeout. The assertions do not change.
- No raised timeouts, no `test.slow()`, and no retries.
- No app code changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Tooling only, so `skip_specs: true`.

## Impact

- `frontend/e2e/ui-foundation.spec.ts`
- `frontend/e2e/settings.spec.ts`
- `frontend/e2e/follow-ups.spec.ts` (added by the approved plan answer, one `exact: true`)
