# Proposal

Delivers GitHub issue #145 (no milestone). Found by the manual end-to-end check (#57).

## Why

An owner cannot connect Slack from Settings. The connect form posts `{ repository: "", consent }` for both providers. `SetupSerializer` accepts a missing `repository` and rejects a blank one, so the Slack request fails with 400 `invalid_request`. The error is on the `repository` field, which the Slack card does not render, so the owner sees only "Could not connect Slack. Check the submitted fields."

`slack-connection` requires that an owner can start Slack installation ("Owner-initiated OAuth installation"). The code diverges from it.

## What Changes

- The Slack connect and reconnect form posts `{ consent }` only.
- The GitHub form keeps posting `{ repository, consent }`.
- Component tests submit the Slack form (first connect and reconnect) and the GitHub form, and assert the request body.
- A browser test submits the Slack form against the real API and asserts the reply is not a validation error.

No backend, API, `frontend/openapi.yaml`, or spec change. A blank repository stays invalid. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The code is brought back in line with `slack-connection`.

## Impact

- `frontend/src/features/settings/connection-settings.tsx` (the setup request body only).
- `frontend/src/features/settings/settings-page.test.tsx` (three new tests and two helpers).
- `frontend/e2e/settings.spec.ts` (one new test).
