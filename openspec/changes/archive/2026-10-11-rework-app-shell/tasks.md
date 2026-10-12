# Tasks

Paths are from the repository root. Decisions D1 to D12 are in `design.md`. The coordinator's answers are in `.claude/answers/plan.md` and are folded into `design.md`. Ports and isolation rules are in `.claude/brief.md`.

## 1. Registry components and tokens

- [x] 1.1 From `frontend`, run `npx shadcn add sidebar dropdown-menu breadcrumb` per D1. Answer no to every overwrite prompt. Verify: `git status` shows new files only (`sidebar.tsx`, `sheet.tsx`, `tooltip.tsx`, `dropdown-menu.tsx`, `breadcrumb.tsx` in `frontend/src/components/ui/`, and `frontend/src/hooks/use-mobile.ts`); `git diff --stat` shows no change to `package.json`, `package-lock.json`, or any existing file in `components/ui/`. If a dependency was added, stop and ask.
- [x] 1.2 Append the alias block from D10 at the end of `frontend/src/styles/theme.css`. Verify: `git diff frontend/src/styles/theme.css` shows only added lines at the end, each value is `var(--...)`, and `npm run test -- theme` passes.
- [x] 1.3 In `frontend/src/components/ui/sidebar.tsx`, remove the `sidebar_state` cookie write and unused `outline` variant (D4 and raw-colour answer). Keep width constants at registry defaults; set issue widths through `SidebarProvider`'s `style` prop. Verify: no cookie reference remains.

## 2. Tracer: the shadcn Sidebar with today's behaviour

- [x] 2.1 Rebuild `frontend/src/components/layout/app-shell.tsx` on `SidebarProvider`, `Sidebar collapsible="icon"`, `SidebarInset`, and `SidebarTrigger`, with no new feature yet. Keep: the skip link first in the document, the wordmark link, the four destinations with their names and icons, `main#main-content` with `tabIndex={-1}`, the content column width, the phone tab bar, and the gallery rules. Desktop rows use `min-h-11` in both states and the width stays 14rem (D2, D3). Verify in `app-shell.test.tsx` (stub `matchMedia` as `theme.test.ts` does): the skip link is the first focusable element, each destination link is found by its exact name, and the wordmark link opens the inbox.
- [x] 2.2 Control `open` from `localStorage` key `rescribo-sidebar` (D4). Put the read and write in `frontend/src/components/layout/sidebar-state.ts`, with storage errors handled the way `src/lib/theme.ts` handles them. Verify in a unit test: default is expanded; toggling writes the key; a stored collapsed value renders the rail; blocked storage does not throw.

## 3. User menu

- [x] 3.1 Add `frontend/src/components/layout/user-menu.tsx` per D6: name and email label, Theme radio group from `[...THEMES, 'system']` bound to `useThemePreference`, separator, Sign out. Do not edit `frontend/src/features/settings/theme-settings.tsx`. The trigger shows avatar, name, and workspace name, and the avatar alone in the rail. In a demo workspace the label area also shows `demoDescription`. Verify in `user-menu.test.tsx`: the menu shows the session's name and email; picking Dark sets `data-theme="dark"` and marks Dark as checked; Escape returns focus to the trigger; the demo sentence shows only when `is_demo` is true.
- [x] 3.2 In `app-shell.tsx`, read the session per D6, render `UserMenu` in the sidebar footer, and remove the header Sign out button. Keep the sign-out mutation and the `role="alert"` message in the header. Under `md`, render an avatar trigger for the same menu at the right of the header, with `touchTarget`. Verify in `app-shell.test.tsx`: no `button` named Sign out exists outside the menu; choosing the Sign out menu item calls `logout` and goes to `/sign-in`; a failed sign-out shows the alert; `/dev/ui` shows no user menu and no Sign out.

## 4. Counts

- [x] 4.1 Add `frontend/src/components/layout/use-navigation-counts.ts` per D7, with the two queries, `NAV_COUNTS_REFRESH_MS = 30_000`, and `enabled` only when a workspace exists. Verify in a unit test with stubbed fetch: it returns the two `count` values; it makes no request without a workspace; invalidating `reportKeys.all(workspaceId)` refetches the report count.
- [x] 4.2 Render the counts as `SidebarMenuBadge` siblings of the Inbox and Follow-ups links, in the sidebar, the rail, and the phone tab bar (D7). Verify in `app-shell.test.tsx`: with counts 3 and 2 the badges show and are announced as "3 new reports" and "2 follow-ups need approval"; the links are still found by the exact names "Inbox" and "Follow-ups"; after both count queries resolve with 0, pending, and failed show no badge; 120 shows "99+".

## 5. Breadcrumbs and header

- [x] 5.1 Add `frontend/src/components/layout/breadcrumbs.tsx` per D8, with the path table, `matchPath`, and the two title queries on the existing detail keys. Do not edit `frontend/src/App.tsx`. Verify in `breadcrumbs.test.tsx`: each row of the D8 table; section links on problem and follow-up pages; the follow-up page report title; the last item has `aria-current="page"`; fallback words show while the title is pending and after a failed request; the title query uses the same key as the page (one request when both are mounted).
- [x] 5.2 In the `app-shell.tsx` header, replace the workspace name and tagline with `SidebarTrigger` (desktop only), `Breadcrumbs`, and the Demo badge with its "Demo workspace" label. Mark the place for the #199 trigger with one comment (D9). Verify in `app-shell.test.tsx`: the Demo badge shows in a demo workspace and not otherwise; the tagline text is gone; the breadcrumb `nav` is named "Breadcrumb".
- [x] 5.3 Hide the wordmark link when the sidebar is collapsed (D5). Verify in `app-shell.test.tsx`: expanded, the link named "rescribo, go to inbox" opens the inbox; collapsed, no such link is rendered and the Inbox destination is still present.

## 6. E2e

- [x] 6.1 Add `frontend/e2e/shell.ts` with `signOut(page)`: open the user menu, choose Sign out. Use it in `accounts.spec.ts` (4 places), `themes.spec.ts` (1), and `ui-foundation.spec.ts`. In `ui-foundation.spec.ts`, change the `aside` locator to the sidebar element and make "sign out is in view on settings" check the user menu trigger. Save one owner session for this spec with `saveSeedSession`'s optional user index (default 1); keep sign-out isolated in an empty context. This avoids the 10 sign-ins per minute login throttle. Change no other line of those files. `accounts.spec.ts` belongs to #202: touch only its four Sign out lines and the import. Verify: `git diff --stat frontend/e2e/accounts.spec.ts` shows five changed lines.
- [x] 6.2 Add to `ui-foundation.spec.ts`: collapse the sidebar, reload, and expect the rail; open a problem and expect the breadcrumb link and title; axe on the shell with the sidebar collapsed and with the user menu open, in light and dark; at 375 px the user menu trigger is at least 44 px and the page does not scroll sideways. Add to `demo.spec.ts`: the Demo label is visible with the sidebar collapsed.

## 7. Docs

- [x] 7.1 Edit `frontend/DESIGN.md` per D12: correct the listed lines, append the new components to the shadcn primitives line, and add the "App shell" section at the end. Verify: `git diff frontend/DESIGN.md` rewords only the lines D12 lists. Copy each reworded line into the PR body.

## 8. Screenshots

- [x] 8.1 With the dev servers on 8198 and 5198, reseed the demo and run `SHOTS_BASE=http://127.0.0.1:5198 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after`. The before shots are in `.claude/shots/before` (42 files). Add a helper in the git-ignored `.claude/shots/` that captures, in light and dark: the inbox with the sidebar collapsed, the user menu open on desktop, the user menu open at 390 px, and a problem page with its breadcrumb. Build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py`. Verify: desktop rows are the same height as before; no page gained horizontal scroll at 390 px. Stop the dev servers afterwards.

## 9. Repository checks

- [x] 9.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 9.2 `task check test build schema-check` passes with PostgreSQL and Redis running. `schema-check` must report no contract change. Record the test counts for the PR.
- [x] 9.3 `RESCRIBO_E2E_API_PORT=8198 RESCRIBO_E2E_FRONTEND_PORT=5198 task e2e` passes. Record the counts for the PR.

## Workflow follow-up

- Archive this change in the PR that completes #198 (`/opsx:archive`).
- The PR closes #198 and #176. Milestone: H. Product-grade UI.
- PR body lists: the reworded DESIGN.md lines, both edits to `sidebar.tsx`, the appended `theme.css` block, and the e2e files touched.
