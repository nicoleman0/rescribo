# Tasks

## 1. Tokens

- [x] 1.1 Add the `[data-theme='dark']` token block with every colour, tone, and elevation value, set `color-scheme` per theme, and bind Tailwind's `dark` variant to `data-theme`; verify `npm run build` and the raw-colour check pass.

## 2. Theme module and pre-paint

- [x] 2.1 Add `src/lib/theme.ts` (theme list, storage key, read, resolve, apply, `startTheme`, `useThemePreference`) and call `startTheme()` from `main.tsx`; verify unit tests cover invalid stored values, system resolution, live system changes, and storage errors.
- [x] 2.2 Add the inline pre-paint script to `index.html`; verify a unit test runs it for each stored value and matches `resolveTheme(readPreference())`.

## 3. Picker

- [x] 3.1 Add the Appearance section with Light, Dark, and System radios at the top of Settings; verify a unit test that choosing Dark sets `data-theme` and the stored value.

## 4. Browser checks and docs

- [x] 4.1 Add e2e tests: dark persists across reload and sign-out, system follows an emulated colour scheme change, and axe reports no violations on the inbox, problem detail, follow-ups, and settings in dark; verify they pass.
- [x] 4.2 Document themes, the dark palette rule, and how to add a theme in `frontend/DESIGN.md`; verify every name it mentions exists in code.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`, `task check test build schema-check` with PostgreSQL and Redis running, and `task e2e`; verify all pass.
- [x] 5.2 Take before/after Playwright screenshots of every screen in light and dark at desktop and phone width.

## Workflow follow-up

- Archive this change in the PR that completes issue #101.
