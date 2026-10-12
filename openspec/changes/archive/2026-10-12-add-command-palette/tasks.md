# Tasks

Paths are from the repository root. Decisions D1 to D11 are in `design.md`. Ports and isolation rules are in `.claude/brief.md`. Answers from the coordinator arrive in `.claude/answers/`; fold them into `design.md` before starting.

## 1. Registry components

- [x] 1.1 From `frontend`, run `npx shadcn add command dialog` per D1. Answer no to every overwrite prompt. Verify: `git status` shows three new files (`command.tsx`, `dialog.tsx`, `input-group.tsx` in `frontend/src/components/ui/`); `git diff frontend/package.json` shows one added line, `cmdk`; no existing `ui/` file changed. Otherwise stop and ask.
- [x] 1.2 Restyle the three new files from the tokens per D2. Verify: `grep -nE "rounded-xl|ring-foreground|bg-black/[0-9]+ |#[0-9a-f]{3,6}" ` over the three files finds only the overlay class shared with `sheet.tsx`; every `animate-`, `fade-`, `zoom-`, and `slide-` class in `dialog.tsx` has a `motion-safe:` prefix; `npm run typecheck` and `npm run lint` pass.
- [x] 1.3 Add the "Command" card to `frontend/src/dev/ui-gallery.tsx` per D10. Verify: `/dev/ui` on port 5199 shows the inline list and the dialog opens and closes with Escape.

## 2. Shortcut registry

- [x] 2.1 Add `frontend/src/lib/shortcuts.ts` per D3. Verify in `shortcuts.test.ts`: Ctrl+K and Cmd+K call the bound handler and prevent the default; K alone, Ctrl+Shift+K, and Ctrl+Alt+K do not; an unbound shortcut does not prevent the default; unmounting unbinds; binding one id twice throws; `shortcutKeys` returns `⌘` for a Mac platform and `Ctrl` otherwise; `boundShortcuts` lists only bound ids.
- [x] 2.2 Remove the key handler and `SIDEBAR_KEYBOARD_SHORTCUT` from `frontend/src/components/ui/sidebar.tsx`, and bind `toggleSidebar` in `ShellContents` with `useShortcut`. Verify: `grep -n keydown frontend/src/components/ui/sidebar.tsx` finds nothing; a new case in `app-shell.test.tsx` shows Ctrl+B collapses the sidebar and writes `rescribo-sidebar`; the existing sidebar shortcut step in `e2e/ui-foundation.spec.ts` is unchanged and passes.

## 3. Tracer: palette that goes to a screen

- [x] 3.1 Move the navigation items to `frontend/src/components/layout/navigation-items.ts` per D5, with no behaviour change. Verify: `app-shell.test.tsx` passes unchanged.
- [x] 3.2 Add `palette-trigger.tsx` and `command-palette.tsx` under `frontend/src/components/command-palette/` with the Go to group only, and mount both in `ShellContents` per D4 and D9. Verify in `command-palette.test.tsx` and `app-shell.test.tsx`: the trigger is named "Open command palette"; Ctrl+K opens the dialog named "Command palette" with focus in the input, and closes it; Ctrl+K opens it from inside a text input; the five screens are listed; typing "prob" and Enter goes to `/problems` and closes the palette; Escape returns focus to the trigger; `/dev/ui` shows no trigger.

## 4. Search

- [x] 4.1 Add `use-palette-search.ts` and the Reports and Problems groups per D6. Verify in `command-palette.test.tsx` with stubbed fetch: one character makes no request; two characters request both lists with `q` after the debounce; at most five rows show per group; choosing a report goes to `/inbox/<id>` and a problem to `/problems/<id>`; a pending search shows "Searching…"; a failed report search shows its retry item while problems and screens still list, and choosing retry repeats only the report request; no match anywhere shows "No results".
- [x] 4.2 Add `frontend/e2e/command-palette.spec.ts` with a saved session from `saveSeedSession`. Cover: Control+K opens, "prob" plus Enter opens problems; a seeded problem title opens that problem; a seeded report title opens that report in the inbox. The e2e seed has one workspace, so the "Another workspace" scenario is covered in `command-palette.test.tsx`: every search request path starts with `workspaces/<the member's workspace id>/`; the endpoints' own isolation tests are in the backend. Verify: the spec passes with `RESCRIBO_E2E_API_PORT=8199 RESCRIBO_E2E_FRONTEND_PORT=5199`, and `ui-foundation.spec.ts` still passes its phone touch-target sweep.

## 5. Theme and shortcut groups

- [x] 5.1 Add the Theme group per D7. Verify in `command-palette.test.tsx`: three items from `[...THEMES, 'system']`; choosing "Dark theme" sets `data-theme="dark"` and closes the palette; reopening marks Dark as current. Add to the e2e spec: choose dark in the palette, open Settings, and the theme choice shows dark.
- [x] 5.2 Add the Shortcuts group and the trigger's key hint per D8 and D9. Verify in `command-palette.test.tsx`: both shortcuts list with `Ctrl` keys on a non-Mac platform and `⌘` on a Mac one; choosing "Toggle sidebar" calls its handler and closes the palette; with `useIsMobile` true the group is absent.

## 6. Accessibility, phone, and motion

- [x] 6.1 Add to `command-palette.spec.ts`: axe on the open palette with search results, in light and dark, with `axeViolations`; at 390px the trigger and each item pass `expectTouchTarget` and `document.documentElement.scrollWidth` is at most `clientWidth`; arrow down twice plus Enter runs the third item; with `reducedMotion: 'reduce'` the dialog has no running animation after opening. Verify: the spec passes.
- [x] 6.2 Add the "Command palette" section at the end of `frontend/DESIGN.md` per D10. Verify: `git diff frontend/DESIGN.md` shows added lines only.

## 7. Screenshots

- [x] 7.1 With the dev servers on 8199 and 5199, reseed the demo and run `SHOTS_BASE=http://127.0.0.1:5199 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after`. The before shots are in `.claude/shots/before`. Add a helper in the git-ignored `.claude/shots/` that captures, in light and dark: the open palette on desktop with nothing typed, with search results, and the open palette at 390px. Build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py`. Verify: the header trigger shows in every signed-in after shot and no page gained horizontal scroll at 390px. Stop the dev servers afterwards.

## 8. Repository checks

- [x] 8.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 8.2 `task check test build schema-check` passes with PostgreSQL and Redis running. `schema-check` must report no contract change. Record the test counts and the build size for the PR.
- [x] 8.3 `RESCRIBO_E2E_API_PORT=8199 RESCRIBO_E2E_FRONTEND_PORT=5199 task e2e` passes. Record the counts for the PR.

## Workflow follow-up

- Archive this change in the PR that completes #199 (`/opsx:archive`).
- The PR closes #199. Milestone: H. Product-grade UI.
- PR body lists: the `cmdk` dependency, the removed handler in `sidebar.tsx`, the three registry files and how they differ from the registry, and the choice to hand-roll the shortcut registry.
