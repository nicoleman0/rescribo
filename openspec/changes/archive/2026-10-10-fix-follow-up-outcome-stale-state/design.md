# Design

## Context

`ContactSection` renders `RecordOutcomeForm`, which stays mounted for as long as the follow-up is open. It offers `choicesFor(outcome.state)`: three options from `pending`, three from `contacted`, none from a terminal state. With no options it renders `CorrectionForm` for an owner, which offers every state except the current one.

Both forms hold the selected value in `useState(choices[0])`. React keeps that value when the choices change. A `<select>` whose value matches no option shows its first option, so the screen and the stored value disagree.

Three paths send a stale value. Each was reproduced in a component test on the current code:

| Path | Sent | Expected |
| --- | --- | --- |
| Record "Customer contacted", then record again (the issue) | `contacted`, with the previous note | `confirmed`, empty note |
| Owner corrects a terminal outcome to `pending`, then records | `pending` | `contacted` |
| Owner corrects `confirmed` to `still_affected`, then corrects again | `still_affected`, with the previous note and reason | `pending`, empty note |

The API rejects all three with 409 `invalid_transition` (`record_outcome` and `correct_outcome` in `backend/feedback/follow_ups.py`).

The existing browser test records contact and then confirmation, but it calls `selectOption` before the second click. That fires a change event and hides the bug.

## Goals / Non-Goals

**Goals:**
- Both forms send the option the dropdown shows, on every path.
- After a save, the note (and the correction reason) is empty.
- A failed save keeps the member's note and still shows the error.
- Tests fail if either form sends a value it does not offer.

**Non-Goals:**
- Backend, API, `frontend/openapi.yaml`, and specs.
- The error text for `invalid_transition`.
- #154, #157, #158, #159, #160, which touch the same folder.
- Merging the two forms or extracting a shared hook.

## Decisions

**Derive the sent value from the offered choices.** Each form stores the member's pick as `choice` (`null` until they pick). The value shown and sent is `choice` if it is among the current choices, otherwise the first choice. The rule "send only what is offered" is stated once per form, where the value is computed, so no path can send a value outside the list.

**Reset on the member's own successful save.** `useFollowUpMutation` already takes an `onSuccess` callback, and `RecipientForm` in the same file resets its `choice` with it. The outcome forms do the same: clear `choice` and the note, and the reason in `CorrectionForm`.

Alternative: `key={followUp.outcome.state}` on `RecordOutcomeForm`, which remounts both forms when the outcome changes. It is one line and matches the issue's wording ("reset when the outcome state changes"). It was prototyped and rejected. When another member changes the outcome first, the save returns 409 with the current row, the outcome state changes, and the remount drops the typed note and the error message. `web-interface` "Draft preservation" says "Unsaved input SHALL survive recoverable failures, including conflicts". A background refetch that brings a new outcome would wipe a half-typed note the same way.

The two approaches behave the same on the issue's path. They differ only when the outcome changes from somewhere other than this form.

**Component tests go in `follow-up-detail.test.tsx`.** Four tests, one per path above plus the conflict case. They need a stub that remembers the follow-up between requests: a successful mutation invalidates the detail query, and the existing stubs would answer the refetch with the original outcome. `stubOutcomes` keeps the current row and returns the request bodies.

**One browser test in `follow-ups.spec.ts`.** It records contact with a note, then clicks "Record outcome" again without touching the form, and asserts the second request's `state` and `note`. It prepares the message without sending, as the "marks a problem reviewed" test does, so it needs no worker round trip. It reuses the saved owner session and adds no sign-in.

**Both kinds of test prove the failure on current code.** The first component test is the fast proof: it asserts the second request body with `toEqual`. The browser test proves the same against the real page and API.

**Prototyped before planning.** The tests and the fix were written, run, and removed:
- Without the fix: the four component tests fail and the other 21 in the file pass. The first receives `state: "contacted", note: "Called Acme"` as the second body. The browser test fails with `state: "contacted", note: "Called the customer"`.
- With the fix: 25 of 25 component tests pass, and `e2e/follow-ups.spec.ts` passes 8 of 8 (6 tests plus 2 setup). `npm run typecheck` and Prettier pass.
- With the `key` alternative instead: three component tests pass and the conflict test fails, because the error message is gone.

## Risks / Trade-offs

- [After a conflict that changes the outcome, the dropdown can move to a different option than the member picked] → The error says the report changed and the latest version is shown. The dropdown and the request agree.
- [A conflict that moves the outcome to a terminal state replaces the record form with the correction form, or with nothing for a non-owner, so the error and the note are not shown] → Existing behaviour, unchanged here. See "Decisions to review" in the PR.
- [The two forms repeat the same three-line pattern] → Accepted. Their choice lists have different shapes, and a shared hook is more code than the repetition.
