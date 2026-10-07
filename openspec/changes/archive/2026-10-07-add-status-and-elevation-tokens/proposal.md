# Proposal

## Why

Issue [#110](https://github.com/nicoleman0/rescribo/issues/110): each feature picks its own badge colours, so the same kind of state reads differently on the inbox, problems, and follow-ups screens, and surfaces have no shared depth scale. The screen reworks in milestone E (#106 to #109) and themes (#101) need these foundations first. Direction and mockup: [#100](https://github.com/nicoleman0/rescribo/issues/100) (Quiet + craft).

## What Changes

- Add six status tones (neutral, info, progress, success, warning, danger) as theme tokens, and one shared status badge that renders a tone with a dot and a text label.
- Map every triage, problem, needs-review, delivery, and contact state to a tone. Remove the per-feature badge colour classes and the `linked` and `needs-review` colour tokens they used.
- Add a three-level elevation scale: resting surfaces, raised panels, floating overlays. Cards use the resting level.
- Colour the sidebar wordmark from the primary token and link it to the inbox. This closes [#98](https://github.com/nicoleman0/rescribo/issues/98).
- Write the Quiet + craft direction (status tones, elevation, wordmark) into `frontend/DESIGN.md`.
- Light theme only. Dark tokens arrive with #101; motion with #106.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds consistent status presentation across screens and wordmark navigation to the inbox.

## Impact

Frontend only: `src/styles/theme.css`, a new shared status badge, the inbox, problems, and follow-ups badge code, `Card`, the wordmark and app shell, the UI gallery, and `frontend/DESIGN.md`. No API, database, or worker changes. No new dependency.
