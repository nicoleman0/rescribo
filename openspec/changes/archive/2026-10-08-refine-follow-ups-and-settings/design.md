# Design

## Context

Follow-up rows render `DeliveryChip` and `ContactChip` side by side with no label. The detail header puts the label inside the badge text ("Contact: Pending", "Delivery: Sent"), while the "Customer contact" section below calls the same value "Outcome". Tone maps for both already live in `follow-ups-format.ts` and stay as they are.

`ConnectionSettings` renders a section with the raw status string (`active`, `error`), a key/value list, and job counts as one sentence. The mockup in #100 has no follow-ups or settings screen, so this change ports its general patterns: status badges, a labelled key/value grid in detail panels, segmented chips with mono counts, and resting cards.

## Goals / Non-Goals

**Goals:**
- One place in the follow-ups feature that pairs each status with its label, used by both the row and the detail.
- One place in the settings feature that maps a connection state to a label and tone.

**Non-Goals:**
- Changing any tone, any action, or what a control does.
- Extracting the bucket chips into a shared component. #107 may share them with the inbox later.
- Restyling members, the Slack account link, or workspace deletion.

## Decisions

### Label outside the badge

A `FollowUpStatuses` component renders a `dl`: a muted "Delivery" or "Outcome" term, then a `StatusBadge` with the plain state label. The badge text stays the state alone, so "Sent" reads the same here as anywhere else, and the term names which status it is. "Outcome" matches the "Customer contact" section and the "Record outcome" control; "Contact: Contacted" read badly.

Alternative considered: keep the label inside the badge, as the detail did. Rejected because the pill gets long, and in rows two long pills wrap on a phone.

### Row layout

On desktop a row is two columns: title and metadata on the left, the status list on the right in a fixed-width column so the badges line up from row to row. Below `md` the status list moves under the metadata. Status stays on the right instead of the left edge used by the inbox mockup, because a follow-up has two statuses and putting both before the title would push the title out of view on a phone.

### Detail header

The customer, fix, version, destination, and outcome note become one `dl` with a fixed term column, like the mockup's detail panel. `Destination` folds into it, which drops one separator.

### Bucket chips

The chips become one segmented control, like the theme picker: a muted track, the pressed chip on the card surface at elevation 1, counts in Geist Mono. The track scrolls sideways when the labels do not fit, so on a phone the list stays near the top. Buttons keep `aria-pressed` and their accessible count labels.

### Connection status

`ConnectionStatusBadge` in `settings/connection-status.tsx`, like `ProblemStateBadge`, maps `active`, `error`, and `disconnected` to "Connected" (success), "Needs attention" (danger), and "Disconnected" (neutral), and a missing connection to "Not connected" (neutral). Error uses danger because the integration is broken and needs action, which is what danger means in DESIGN.md.

### Integration cards

Each provider renders inside the shared `Card` (elevation 1). The header holds the provider name and the status badge. Details use the same fixed-term `dl`. Job counts are a four-cell `dl` with the number in Geist Mono above its label. Counts stay in the foreground colour: they are not statuses, and a coloured zero would be noise. Forms, consent, channels, and disconnect stay inside the card in their current order.

## Risks / Trade-offs

- [The row's accessible name grows to include "Delivery Sent Outcome Pending"] → It names both states, which a screen reader user needs. Tests match the title by regular expression.
- [A sideways-scrolling chip track can hide chips on a phone] → The pressed chip and the first few stay visible, and the track keeps keyboard focus order.
