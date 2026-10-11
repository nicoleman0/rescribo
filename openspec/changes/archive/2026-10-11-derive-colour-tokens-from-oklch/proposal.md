# Proposal

Delivers GitHub issue #197 (milestone H. Product-grade UI).

## Why

Every colour token in `frontend/src/styles/theme.css` is a hand-picked hex value, repeated per theme. A new palette (#203) would need about 50 new values for each of its light and dark blocks, and nothing keeps them consistent.

## What Changes

- Each theme block gains three palette variables: `--brand-hue`, `--brand-chroma`, and `--neutral-tint`.
- The 20 surface, border, text, and brand tokens become `oklch()` values built from those variables. Each token keeps its own lightness, and a neutral token takes a whole-number multiple of the tint.
- The 18 status tone tokens and `--destructive` stay fixed hex values. They do not read the palette variables. `--tone-info-dot` keeps its own value.
- Token names, the `@theme` mapping, shadows, and elevation do not change.
- A new browser test resolves every colour token in light and dark and compares it with the colour on `main`. A derived token may differ by at most 1/255 per channel. A fixed token must match exactly.
- The unit test that compares theme blocks learns the `oklch()` form. It also requires the palette variables in every block and hex values for the fixed tokens.
- `frontend/DESIGN.md` gains a short Palette section.

No rendered colour moves by more than 1/255 per channel. No behaviour, API, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `frontend/src/styles/theme.css`: the colour lines of the `:root` and `:root[data-theme='dark']` blocks. Nothing below the dark block changes, so #198 can append its sidebar aliases at the end of the file.
- `frontend/src/lib/theme.test.ts`: the theme block test.
- `frontend/e2e/theme-tokens.spec.ts`: new.
- `frontend/DESIGN.md`: one new section.
- Out of scope: new palettes, the palette picker, and per-palette contrast checks (#203); sidebar tokens (#198).
