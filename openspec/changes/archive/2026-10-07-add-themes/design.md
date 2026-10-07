# Design

## Context

`theme.css` defines one token set on `:root`. Every colour in the app comes from those tokens; `scripts/check_raw_colours.py` rejects literals elsewhere. Tailwind's `dark:` variant defaults to the media query, and the source uses no `dark:` classes today. The wordmark is already a mask over `--primary` (#110). Nothing in the app stores preferences.

Decided with the maintainer on 7 October 2026: the choice is stored in the browser, and the picker lives in Settings.

## Goals / Non-Goals

**Goals:**
- One CSS block per theme, selected by `data-theme` on `<html>`. A new theme is a new block plus one entry in the theme list.
- No flash of the wrong theme on load.

**Non-Goals:**
- Storing the choice on the account or syncing it across devices.
- A picker in the shell or on the sign-in page.
- Theming the marketing site.
- Motion (#106) or layout changes.

## Decisions

### `data-theme` always holds a concrete theme

`:root` keeps the light values and `:root[data-theme='dark']` redefines every colour token, with `color-scheme` set in each. "System" is resolved in script to `light` or `dark` before it reaches the attribute. That keeps one block per theme. The alternative, a `prefers-color-scheme` media block next to the attribute block, repeats the dark values twice.

`index.css` declares `@custom-variant dark (&:where([data-theme='dark'], [data-theme='dark'] *))` so any `dark:` class, including shadcn's shimmer, follows the picker rather than the OS.

### Theme module

`src/lib/theme.ts` owns the theme list, the storage key, reading and validating the saved preference, resolving system, applying it to `<html>`, and a `useThemePreference` hook. `main.tsx` calls `startTheme()` once, which applies the preference and listens for `prefers-color-scheme` changes and `storage` events from other tabs.

### Pre-paint script

A classic inline script in `index.html` reads the storage key, resolves system with `matchMedia`, and sets `data-theme` before the stylesheet paints. It cannot import the module, so it repeats the key and the system rule in four lines. A unit test runs the script from `index.html` against each stored value and asserts it sets the same theme as `resolveTheme(readPreference())`. An unknown stored value is applied as-is, matches no block, and renders light until `startTheme()` corrects it. There is no Content-Security-Policy today; if one is added, the script needs a hash.

Alternative considered: load a `public/theme.js` file that exposes a global API for the module to call. Rejected: it adds a global and a second untyped file without removing the need for a pre-paint step.

### Picker

An Appearance section at the top of Settings, visible to every role. A `fieldset` with a legend and three radio inputs (Light, Dark, System), styled as a segmented control. Radios give arrow-key navigation and a clear selected state without a custom widget. Changing it applies at once; there is no save button.

### Dark palette

Values come from the #100 mockup:

| Token | Dark |
|---|---|
| background, sidebar, card | `#0f0f14`, `#131319`, `#17171f` |
| foreground, muted-foreground | `#ececf1`, `#a0a0ae` |
| border, input | `#26262f`, `#34343f` |
| muted, secondary, accent | `#1d1d26` |
| selected | `#23233a` |
| primary, ring, primary-foreground | `#8b8cf5`, `#8b8cf5`, `#101018` |
| destructive | `#ffa399` (the mockup's danger text) |

Inputs use the mockup's stronger border, because the plain dark border is too faint for a field edge. Tones and elevation use the mockup's dark sets. The dark elevation rings use `--border`, except level 3, which uses `--input` (the stronger border), as in the mockup.

## Risks / Trade-offs

- [The inline script and the module can drift] → The consistency test fails if either changes alone.
- [Per-browser choice does not follow a person to a new device] → Accepted; system is a reasonable default.
- [Dark contrast regressions] → An e2e axe run on dark screens covers contrast.
