# Proposal

## Why

Issue [#203](https://github.com/nicoleman0/rescribo/issues/203): members can choose light, dark, or system, but not a colour. Builds on the palette variables from #197.

## What Changes

- Add four palettes: indigo (the current colours, and the default), forest, autumn, and sky. Each has values for light and dark.
- A palette sets the brand colour, focus ring, selection, and neutral tint. Status tones and destructive stay fixed in every palette.
- Add a palette choice beside the theme choice. It is saved in this browser under its own key, survives sign-out, and applies before first paint.
- Add a swatch picker under Settings, Appearance.
- Add a contrast check that covers every palette in light and dark and runs in `task e2e`.
- Update the Palette section of `frontend/DESIGN.md` and its "Do not add a second palette" rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a palette choice that persists per browser and applies before first paint, and a contrast requirement for every palette in every theme.

## Impact

Frontend only: `src/styles/theme.css`, `src/lib/theme.ts` and its test, `index.html`, `src/features/settings/theme-settings.tsx`, `e2e/theme-tokens.spec.ts`, `e2e/themes.spec.ts`, and `frontend/DESIGN.md`. No API, database, or worker changes. No new dependency. The palette is per browser, like the theme; it is not saved on the server or per workspace.
