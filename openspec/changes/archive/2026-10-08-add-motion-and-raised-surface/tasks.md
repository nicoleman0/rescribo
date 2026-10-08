# Tasks

## 1. Tokens and utilities

- [x] 1.1 Add the duration, easing, and stagger tokens to `:root` in `src/styles/theme.css`, and the motion utilities from design decision 1, each inside `@media (prefers-reduced-motion: no-preference)`; verify `npm run build` passes and the built CSS contains `animate-page-enter` and `stagger-rows`.
- [x] 1.2 Add `--raised`, `--raised-muted`, and `--shadow-hairline` to both theme blocks, expose `bg-raised` and `shadow-hairline`, and add the `surface-raised` utility; verify `theme.test.ts` passes and fails if the dark `--raised` line is removed.

## 2. Shared components

- [x] 2.1 Add `ReadyState` to `src/components/states/async-states.tsx` and render it from `QueryState`'s ready branch; verify unit tests show it forwards `aria-busy` and `className` and carries `animate-content-enter`.
- [x] 2.2 In `Button`, replace `translate-y-px` with `press`, replace `transition-all` with colour, border, and shadow transitions at `--duration-fast`, and add `shadow-hairline` to `outline` and `secondary`; verify a unit test checks the classes and the UI gallery shows the outline shadow.
- [x] 2.3 Add `transition-status` to `StatusBadge` and its dot; verify `status-badge.test.tsx` asserts it.
- [x] 2.4 Use `surface-raised` on the auth card; verify the dark sign-in screenshot shows `#1c1c25`.

## 3. Feature screens

- [x] 3.1 Add `animate-page-enter` to the roots of the inbox, manual report, problems, problem detail, follow-ups, and settings pages; verify in the browser that opening a report does not replay it.
- [x] 3.2 Replace the ready wrappers at the feature `LoadingState` call sites listed in design decision 3 with `ReadyState`; verify existing feature unit tests pass and `grep -rn "<LoadingState" src/features` matches a `ReadyState` in the same component.
- [x] 3.3 Add `stagger-rows` to the inbox, problems, and follow-ups `ul`; verify in the browser that a refetch leaves existing rows still.
- [x] 3.4 Wrap the report and follow-up panels in the unkeyed `animate-panel-enter` slot, move `lg:sticky lg:top-6` to the report slot, and swap `bg-card` for `surface-raised` on both sections; verify the report panel still sticks while the list scrolls on desktop.
- [x] 3.5 Show the raised surface, the outline hairline, and a replayable motion sample in `src/dev/ui-gallery.tsx`; verify the gallery renders in light and dark.

## 4. End-to-end checks and docs

- [x] 4.1 Add `e2e/motion.spec.ts` with the checks in design decision 9: panel slot animates once and is reused on switch, reduced motion removes animation and scale, dark panel and list surfaces differ, no axe contrast violations with the dark panel open.
- [x] 4.2 Append a Motion section to `frontend/DESIGN.md` (tokens, the six utilities, when each applies, reduced motion, `ReadyState`) and add the raised surface to the level-2 Elevation line; verify every token and utility it names exists in `theme.css`.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict`; verify it passes.
- [x] 5.2 Run `task check test build schema-check` with PostgreSQL and Redis running; verify all pass.
- [x] 5.3 Run `RESCRIBO_E2E_API_PORT=8106 RESCRIBO_E2E_FRONTEND_PORT=5106 task e2e`; verify all pass.
- [x] 5.4 Take after screenshots with `.claude/skills/work-issues/scripts/shots.mjs` and build `.claude/shots/compare.html`; verify the dark panels, sign-in card, and outline buttons differ from the before shots as expected.

## Workflow follow-up

- Archive this change in the PR that completes issue #106.
