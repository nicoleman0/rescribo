## 1. Shared focus style

- [x] 1.1 Add `@utility focus-ring` (`outline: 2px solid var(--ring); outline-offset: 2px`) and `@utility focus-ring-inset` (same, `outline-offset: -2px`) to `frontend/src/styles/theme.css`. Verify: `npm run build` from `frontend` passes.
- [x] 1.2 In `frontend/src/index.css`, move the `button:focus-visible, a:focus-visible` rule into `@layer base` and build it with `@apply focus-ring`. Verify: on `/sign-in` a focused link still shows the 2px `--ring` outline.

## 2. Replace the halo

- [x] 2.1 `button.tsx`: replace `outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50` with `focus-visible:focus-ring`; remove the destructive variant's `focus-visible:border-destructive/40 focus-visible:ring-destructive/20`. Keep the `aria-invalid` classes.
- [x] 2.2 `badge.tsx`: replace `focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50` with `focus-visible:focus-ring`; remove the destructive variant's `focus-visible:ring-destructive/20`.
- [x] 2.3 `input.tsx`, `textarea.tsx`, `native-select.tsx`: replace `focus-visible:ring-3 focus-visible:ring-ring/50` with `focus-visible:focus-ring`.
- [x] 2.4 `input-group.tsx`: replace the control-focus `border-ring`, `ring-3`, and `ring-ring/50` variants with `has-[[data-slot=input-group-control]:focus-visible]:focus-ring`. Leave the `in-data-[slot=combobox-content]` and `aria-invalid` classes.
- [x] 2.5 `app-shell.tsx` wordmark link: replace `focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none` with `focus-visible:focus-ring`.
- [x] 2.6 List rows: `report-list.tsx`, `problems-page.tsx`, `follow-ups-page.tsx` (row): replace `focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset` with `focus-visible:focus-ring-inset`. `problem-picker.tsx`: replace the `has-focus-visible:` ring classes with `has-focus-visible:focus-ring-inset`.
- [x] 2.7 Segmented options: `status-chips.tsx` and `follow-ups-page.tsx` (tabs): replace `focus-visible:ring-3 focus-visible:ring-ring/50` with `focus-visible:focus-ring-inset`. `theme-settings.tsx`: replace the `has-focus-visible:` ring classes with `has-focus-visible:focus-ring-inset`.
- [x] 2.8 Verify: `grep -rn "ring-ring/" frontend/src` returns nothing outside test files. In the dev server, Tab through Inbox (chips, rows), Problems (rows, picker), Follow-ups (tabs, rows), Settings (theme, palette), the member picker, and the sign-in form, in light and dark. Each focused element shows one solid ring and none is cut off.

## 3. Checks and docs

- [x] 3.1 `frontend/e2e/theme-tokens.spec.ts`: hold `--ring` to 3:1 over the full `SURFACES` list. Verify: test passes for all palettes and themes.
- [x] 3.2 Same file: add a test that tabs to the email input and the submit button on `/sign-in` and asserts a solid 2px outline whose painted colour equals the painted `--ring` at full alpha, and no `ring-ring/50` box-shadow. Wait out the `press` transition before reading styles. Verify: the test fails on `main` and passes on this branch.
- [x] 3.3 Add a short Focus section to `frontend/DESIGN.md`: one indicator, the two utilities and when to use each, the base-layer rule for buttons and links. Do not reword other sections.

## 4. Repository checks

- [x] 4.1 Run `task check test build schema-check` with PostgreSQL and Redis running. All pass.
- [x] 4.2 Run `RESCRIBO_E2E_API_PORT=8225 RESCRIBO_E2E_FRONTEND_PORT=5225 task e2e`. All pass.
- [x] 4.3 Run `npx @fission-ai/openspec validate --all --strict`. Passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
- PR Screenshots: note that plain page shots cannot show focus states.
