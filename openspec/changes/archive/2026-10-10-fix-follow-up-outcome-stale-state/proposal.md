# Proposal

Delivers GitHub issue #153 (no milestone). Found by the manual end-to-end check (#57).

## Why

A member records "Customer contacted" on a follow-up and then clicks "Record outcome" again. The dropdown shows "Customer confirmed", but the form sends `{"state":"contacted","note":"","expected_version":2}` and the API answers 409 `invalid_transition`. The member has to reload the page.

The outcome forms keep the selected value in state that is set once. When the outcome changes, the list of choices changes, the browser shows the first remaining option, and the stored value is no longer in the list. The note is kept after a save as well.

`web-interface` requires that recording a customer outcome saves it ("Act on the full page"). The code diverges from it.

## What Changes

- The record-outcome form sends the option the dropdown shows. After a save it clears the note and returns to the first choice.
- The owner's correction form gets the same fix. It goes stale the same way (see design).
- A failed save keeps the note, as `web-interface` "Draft preservation" requires.
- Four component tests and one browser test record two outcomes in a row without a reload and assert the request bodies.

No backend, API, `frontend/openapi.yaml`, or spec change. Nothing rendered changes. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The code is brought back in line with `web-interface`.

## Impact

- `frontend/src/features/follow-ups/follow-up-detail.tsx` (`RecordOutcomeForm` and `CorrectionForm` only).
- `frontend/src/features/follow-ups/follow-up-detail.test.tsx` (four new tests and their helpers).
- `frontend/e2e/follow-ups.spec.ts` (one new test).
