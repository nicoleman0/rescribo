# Proposal

## Why

Issue [#106](https://github.com/nicoleman0/rescribo/issues/106): screens swap instantly, skeletons snap to content, and a status change in a list gives no signal, so state changes are easy to miss. In dark, the level-2 panels sit on the same colour as resting cards and barely separate. Direction and mockup: [#100](https://github.com/nicoleman0/rescribo/issues/100) (Quiet + craft). Builds on [#110](https://github.com/nicoleman0/rescribo/issues/110) (status tones and elevation).

## What Changes

- Add motion tokens to the theme: durations 100, 160, and 220ms and one easing curve.
- Page change: the page fades in with a 4px rise on a real route change. Opening or switching a report or follow-up on the same page does not replay it.
- Skeleton to content: loaded content fades in where the shared loading state was, on every screen that uses it.
- List rows in the inbox, problems, and follow-ups lists enter with a fade, a 4px rise, and a 22ms stagger, capped at 10 rows. Rows animate when they mount, so a background refresh animates only new rows. Settings lists do not stagger.
- Detail panels (report, follow-up) slide 12px in with a fade when they open from no selection. Switching between items only fades the panel content.
- Status badges transition their colours when the status changes.
- Buttons scale slightly on press instead of moving down 1px. Outline and secondary buttons get a hairline shadow.
- Add a raised surface colour for level-2 panels: report detail, follow-up detail, and the sign-in card. Dark uses `#1c1c25` against the `#17171f` card colour. Light stays white.
- All motion is off under `prefers-reduced-motion`. Colour and shadow still change, without a transition.
- Dropped from the issue: the hover lift on link cards. No card in the app is a link (maintainer decision, 8 October 2026).
- CSS and the existing `tw-animate-css` only. No new dependency.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds motion that confirms page, loading, list, panel, and status changes and respects reduced motion, and a raised surface for level-2 panels.

## Impact

Frontend only: `src/styles/theme.css`, the shared async states, `Button`, `StatusBadge`, the auth layout, the inbox, problems, follow-ups, settings, and manual report pages, the UI gallery, e2e checks, and an appended Motion section in `frontend/DESIGN.md`. No API, database, or worker changes. No new dependency.
