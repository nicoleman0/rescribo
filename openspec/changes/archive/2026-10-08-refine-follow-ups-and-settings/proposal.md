# Proposal

## Why

Issue [#109](https://github.com/nicoleman0/rescribo/issues/109): follow-up rows show two unlabelled badges, employee delivery and customer outcome, that look alike, so a "Sent" row cannot be told from a "Confirmed" one without reading closely. Settings shows each integration as key/value text and its job counts as a sentence. Direction and mockup: [#100](https://github.com/nicoleman0/rescribo/issues/100) (Quiet + craft). Builds on the status tones from #110.

## What Changes

- Follow-up rows and the follow-up detail label each status: "Delivery" for the employee message and "Outcome" for the customer contact. A row with no prepared message shows delivery as "Not prepared", as the detail already does.
- The detail header shows customer, fix, version, destination, and outcome note as one labelled list, matching the mockup's detail panels.
- Bucket chips become one segmented control with mono counts, and pagination uses the shared button.
- Settings shows Slack and GitHub each as a card: name, a status badge (Connected, Needs attention, Disconnected, Not connected), identity, repository, last sync, and job counts as four labelled numbers. Owner actions stay inside the card, unchanged.
- Remove the unused `contactStateOrder` constant.
- Appearance stays the first settings section. No motion (#106).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds labelled follow-up statuses and integration status cards.

## Impact

Frontend only: `src/features/follow-ups/` and `src/features/settings/`, their unit tests, the follow-ups e2e assertion on the delivery label, and a new section in `frontend/DESIGN.md`. No API, database, worker, or shared component changes.
