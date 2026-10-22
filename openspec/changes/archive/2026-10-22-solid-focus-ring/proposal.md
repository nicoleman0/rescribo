## Why

Delivers #225. Focus halos use `ring-ring/50`, the ring token at 50% opacity. In indigo the halo is about 2.1:1 in light and 2.5:1 in dark, below the 3:1 that `web-interface` already asks for under "Readable text in every palette". Inputs, list rows, and segmented controls draw only the halo. Buttons and links draw three indicators at once: a solid border, the halo, and the global 2px outline from `index.css`.

## What Changes

- Add one shared focus style: a 2px solid `--ring` outline, as the utilities `focus-ring` (outside the element) and `focus-ring-inset` (inside it).
- Move the global `button`/`a` focus rule into the base layer and build it from `focus-ring`, so component classes can replace it instead of stacking on it.
- Replace `ring-ring/50` in all 13 files with `focus-ring` or `focus-ring-inset`. Buttons and badges lose the `border-ring` focus border and the halo.
- Extend the `--ring` contrast check to every surface a ring can sit on, and add a check that a focused input and button draw the solid `--ring` colour.
- Add a short Focus section to `frontend/DESIGN.md`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The existing requirement "Readable text in every palette" already sets 3:1 for the focus ring. This change makes the code meet it, so `skip_specs: true`.

## Impact

- `frontend/src/styles/theme.css`, `frontend/src/index.css`.
- `frontend/src/components/ui/`: `button.tsx`, `badge.tsx`, `input.tsx`, `textarea.tsx`, `native-select.tsx`, `input-group.tsx`.
- `frontend/src/components/layout/app-shell.tsx`.
- `frontend/src/features/`: `inbox/report-list.tsx`, `inbox/status-chips.tsx`, `problems/problems-page.tsx`, `problems/problem-picker.tsx`, `follow-ups/follow-ups-page.tsx`, `settings/theme-settings.tsx`.
- `frontend/e2e/theme-tokens.spec.ts`, `frontend/DESIGN.md`.
- No API, data, or dependency changes.
