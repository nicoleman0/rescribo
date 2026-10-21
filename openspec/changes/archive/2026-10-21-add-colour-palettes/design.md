# Design

## Context

`theme.css` builds every surface, border, text, and brand token from three palette variables: `--brand-hue`, `--brand-chroma`, `--neutral-tint` (#197). The light values sit in `:root` and the dark values in `:root[data-theme='dark']`. `--primary` and `--ring` hard-code their lightness (0.541 light, 0.685 dark). Status tones and `--destructive` are fixed hex values.

`theme.ts` owns the theme list, storage key, read, resolve, apply, and the React hook. The `theme-boot` script in `index.html` repeats the key and the system rule, and a unit test runs it against the module. `e2e/theme-tokens.spec.ts` pins every indigo token to its pre-#197 colour.

`text-primary` is used as link and label text on cards, the background, and selected rows, so the brand colour must pass 4.5:1 as text, not only as a button fill.

## Goals / Non-Goals

**Goals:**
- One home for each palette value, used by both the page and the swatches.
- Indigo paints exactly as today.
- A failing palette fails `task e2e` with the token pair and ratio.

**Non-Goals:**
- A palette choice in the user menu or the command palette. Both offer the theme today; they stay theme-only (see Open Questions).
- Server-side or per-workspace palettes.
- Changing the focus-ring halo opacity (see Risks).

## Decisions

### A fourth palette variable: `--brand-lightness`

At the current light lightness (0.541), forest and sky brand text drops to about 4.1:1 on the light surfaces, because greens and cyans carry more luminance than indigo at the same OKLCH lightness. Each palette therefore sets the lightness of `--primary` and `--ring`. `--primary` and `--ring` become `oklch(var(--brand-lightness) var(--brand-chroma) var(--brand-hue))`. Indigo keeps 0.541 and 0.685, so its painted values do not change.

Alternative: one lower lightness for every palette. Rejected: it would change indigo and break the pinned reference.

### Palette blocks own the palette variables

The palette variables move out of the `:root` and dark token blocks into one block per palette and theme. Each selector matches both `<html>` and any element inside it that carries `data-palette`:

```css
:root, :root [data-palette='indigo'] { /* indigo light */ }
:root[data-theme='dark'], :root[data-theme='dark'] [data-palette='indigo'] { /* indigo dark */ }
:root[data-palette='forest'], :root [data-palette='forest'] { /* forest light */ }
:root[data-theme='dark'][data-palette='forest'], :root[data-theme='dark'] [data-palette='forest'] { /* forest dark */ }
```

Specificity does the rest: a dark palette block (0,3,0) beats both its light block and dark indigo (0,2,0), and a light palette block beats `:root` (0,1,0). With no `data-palette`, the page falls back to indigo. Each block sets all four variables.

The token blocks keep every token and its lightness. Only the palette variables move.

Alternative: palette blocks scoped to `:root` only, plus separate swatch tokens. Rejected: the swatch colours would repeat each palette's values.

### Swatches read the same blocks

Each swatch is an element with `data-palette="<name>"`. A `palette-swatch` utility in `theme.css` paints `background-color: oklch(var(--brand-lightness) var(--brand-chroma) var(--brand-hue))` on that element. Custom properties resolve where they are declared, so `--primary` on `<html>` cannot be reused for a swatch; the utility repeats its one-line formula instead. A swatch always shows its palette in the current theme, and no colour lives outside `theme.css`.

### Proposed palette values

Lightness and chroma were solved so brand text clears 4.6:1 on the lowest-contrast surface (`--selected` in light) with margin over 4.5, and every value stays inside sRGB. Status hues for comparison, in OKLCH: danger 28, warning 60 to 73, success 156, progress 251 to 255, info 277 to 281 (info already shares indigo's hue).

| Palette | Theme | Hue | Chroma | Lightness | Tint | Brand | Brand text min | Button text | Muted text min |
|---|---|---|---|---|---|---|---|---|---|
| indigo | light | 278 | 0.184 | 0.541 | 0.004 | `#5b5bd6` | 4.55 | 5.35 | 5.09 |
| indigo | dark | 281 | 0.152 | 0.685 | 0.008 | `#8b8cf5` | 5.20 | 6.45 | 5.98 |
| forest | light | 182 | 0.091 | 0.513 | 0.004 | `#04786b` | 4.62 | 5.41 | 5.06 |
| forest | dark | 182 | 0.105 | 0.685 | 0.008 | `#3baf9f` | 5.55 | 7.00 | 5.91 |
| autumn | light | 355 | 0.120 | 0.539 | 0.004 | `#a34d72` | 4.61 | 5.43 | 5.12 |
| autumn | dark | 355 | 0.130 | 0.685 | 0.008 | `#d7769e` | 5.09 | 6.29 | 5.99 |
| sky | light | 230 | 0.095 | 0.515 | 0.004 | `#187193` | 4.69 | 5.50 | 5.07 |
| sky | dark | 230 | 0.105 | 0.685 | 0.008 | `#4aa6ce` | 5.45 | 6.84 | 5.94 |

- Forest is a pine teal at hue 182, 26 degrees from success, at lower chroma than the success dot.
- Autumn is a plum at hue 355, in the widest free gap (info 281 to danger 28), 33 degrees from danger.
- Sky is a deep cerulean at hue 230, 21 degrees from progress. sRGB caps its light chroma near 0.10, so light sky is darker than its name suggests.
- Every palette uses indigo's tints, so neutrals change hue but not strength.

Alternatives for autumn, both computed to pass the same thresholds: copper (hue 50, `#9c5930` light, `#cc8858` dark), the most autumnal but 10 degrees from the warning text `#8a4b00`; ochre (hue 95, `#7c6915` light, `#af9942` dark), 22 degrees from the dark warning dot.

The contrast numbers above are from an sRGB model of the token formulas. The e2e check below is the authority.

### Preference module

`theme.ts` gains `PALETTES = ['indigo', 'forest', 'autumn', 'sky']`, `PALETTE_STORAGE_KEY = 'rescribo-palette'`, `readPalette`, `setPalette`, and `usePalettePreference`. Indigo removes the key, as system does for the theme. An unknown stored value reads as indigo. `apply()` sets `data-theme` and `data-palette` together, and the one storage listener in `startTheme` reacts to either key. The blocked-storage fallback keeps a separate in-page value per preference.

The theme and palette stores share their read, write, and fallback logic through one small internal helper. That refactor lands first, with the existing tests passing unchanged, and the palette is added after it.

### Boot script

`theme-boot` also reads `rescribo-palette` and sets `data-palette`, falling back to `indigo` for a missing or unknown value. It repeats the key and the palette list, with a comment naming `theme.ts`, as it does for the theme. The existing boot test runs for every palette value, plus null and an unknown value.

The current boot script copies an unknown stored theme (for example `sepia`) into `data-theme` until the app bundle corrects it. The palette path validates; whether to fix the theme path here is question 4 in the plan summary.

### Picker

`ThemeSettings` gains a second fieldset, legend "Palette", below Theme. It uses the same segmented control as Theme: native radios (`sr-only`), each label holding a 12px round `palette-swatch` with `data-palette` and the palette name. Native radios give arrow-key selection. Labels keep `touchTarget`. The helper text under Theme moves under both groups, unchanged.

### Contrast check

A new test in `e2e/theme-tokens.spec.ts` loads `/sign-in` once per palette and theme (8 loads), with the palette set in `localStorage` before load and the theme by `emulateMedia`. It reuses the canvas probe already in that file to read painted sRGB, computes WCAG 2.1 relative luminance and contrast, and fails with every pair below its threshold, named by palette, theme, tokens, and ratio.

Pairs, for every palette in light and dark:

- 4.5:1, text on surface: `--foreground`, `--muted-foreground`, and `--primary` on each of `--background`, `--sidebar`, `--card`, `--raised`, `--raised-muted`, `--muted`, `--selected`.
- 4.5:1, paired foregrounds: `--card-foreground` on `--card`, `--secondary-foreground` on `--secondary`, `--accent-foreground` on `--accent`, `--primary-foreground` on `--primary`, `--destructive-foreground` on `--destructive`.
- 3:1, non-text: `--ring` on `--background`, `--card`, and `--raised`.

Status tone pairs are left out: they do not vary by palette, and the unit test pins them as fixed hex.

The existing indigo reference test stays unchanged and runs with no stored palette.

Alternative: a Vitest check that parses `theme.css` and converts OKLCH in TypeScript. Rejected: it reimplements the browser's variable resolution and colour conversion, and could pass while the painted colour fails.

## Risks / Trade-offs

- [Forest, autumn, or sky read as a status anyway] → The coordinator reviews the hues above; changing one is a value edit in one block, and the contrast check reruns.
- [Focus ring halo] → Buttons draw the ring as `ring-ring/50`. At 50% alpha, indigo's halo is already about 2.5:1 in dark and lower in light, so the check measures the solid `--ring` token. The halo opacity lives in shared components and is out of scope; flag it as a follow-up issue.
- [Parallel #201 moves `ThemeSettings` to `/settings/appearance`] → This change does not touch the route. The new e2e steps open Settings the same way `themes.spec.ts` does today; whichever branch merges second updates the path.
- [Moving the palette variables out of the token blocks] → The unit test that each theme block sets the palette variables becomes a test that each palette has a light and a dark block setting all four.
