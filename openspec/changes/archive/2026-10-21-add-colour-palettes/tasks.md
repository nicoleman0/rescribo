# Tasks

## 1. Shared preference store (refactor, no behaviour change)

- [x] 1.1 Extract the read, write, and blocked-storage fallback in `src/lib/theme.ts` into one internal helper used by the theme; verify `src/lib/theme.test.ts` passes unchanged and commit this step on its own.

## 2. Palette tokens

- [x] 2.1 Add `--brand-lightness` and build `--primary` and `--ring` from it; move the palette variables out of the `:root` and dark token blocks into indigo light and dark palette blocks with the selectors in design.md; verify `e2e/theme-tokens.spec.ts` passes unchanged.
- [x] 2.2 Add the forest, autumn, and sky blocks for light and dark with the values in design.md, and the `palette-swatch` utility; verify `python3 scripts/check_raw_colours.py` passes.
- [x] 2.3 Replace the unit test "every theme block sets the palette variables" with one that every palette in `PALETTES` has a light and a dark block setting all four variables; verify it fails when one block is removed.

## 3. Palette preference and pre-paint

- [x] 3.1 Add `PALETTES`, `PALETTE_STORAGE_KEY`, `readPalette`, `setPalette`, and `usePalettePreference` to `theme.ts`; make `apply()` set `data-palette` and the storage listener react to either key; verify unit tests cover the indigo default, an unknown stored value, removing the key for indigo, another tab's change, and blocked storage.
- [x] 3.2 Extend the `theme-boot` script in `index.html` to set `data-palette` with the key and list repeated under a cross-reference comment; verify the boot test agrees with the module for null, every palette, and an unknown value.

## 4. Swatch picker

- [x] 4.1 Add the Palette fieldset to `theme-settings.tsx` as design.md describes; verify a unit test that choosing Forest checks it, sets `data-palette`, and stores the value, and that each option's accessible name is its palette name.

## 5. Browser checks and docs

- [x] 5.1 Add the contrast test to `e2e/theme-tokens.spec.ts` for every palette in light and dark, with the pairs and thresholds in design.md; verify it passes, and that it fails with a named pair when forest light lightness is raised to 0.541.
- [x] 5.2 Add e2e tests to `e2e/themes.spec.ts`: a forest choice persists across reload with the app bundle blocked and across sign-out; autumn with a switch to dark keeps autumn; a status badge paints the same in indigo and forest; axe reports no violations on Settings in forest light and dark; verify they pass.
- [x] 5.3 Update the Palette section of `frontend/DESIGN.md` to describe palettes, their blocks, `--brand-lightness`, and how to add one, and change the "Do not add a second palette" rule to point to that section; leave the rest of the file unchanged and verify every name it mentions exists in code.

## 6. Repository checks

- [x] 6.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `RESCRIBO_E2E_API_PORT=8203 RESCRIBO_E2E_FRONTEND_PORT=5203 task e2e`; verify all pass.
- [x] 6.2 Take the after screenshots with `shots.mjs` into `.claude/shots/after` and build `.claude/shots/compare.html`.

## Workflow follow-up

- Archive this change in the PR that completes issue #203.
