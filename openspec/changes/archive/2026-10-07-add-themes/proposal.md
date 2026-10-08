# Proposal

## Why

Issue [#101](https://github.com/nicoleman0/rescribo/issues/101): the app has one light theme, and nothing follows the system preference. Members who work at night or in dark environments get bright screens. Direction and dark palette: [#100](https://github.com/nicoleman0/rescribo/issues/100). Builds on the tone and elevation tokens from #110.

## What Changes

- Add a dark token set covering every colour, status tone, and elevation token, using the #100 mockup's dark palette.
- Add light, dark, and system themes. System follows the operating system and updates when it changes.
- Add an Appearance section to Settings with a three-way theme picker.
- Remember the choice in this browser. It survives sign-out and applies on the sign-in page.
- Apply the saved theme before the first paint, so a dark choice never flashes light.
- Structure themes so another one needs only a new token set and an entry in the picker list.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a theme choice that persists per browser and follows the system when set to system.

## Impact

Frontend only: `src/styles/theme.css`, `index.css`, `index.html`, a new theme module, the Settings page, `frontend/DESIGN.md`, and browser tests. No API, database, or worker changes. No new dependency. The choice is per browser, as decided on 7 October 2026; it does not follow a person across devices.
