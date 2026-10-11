# Design

## Context

`frontend/src/components/layout/app-shell.tsx` holds the whole shell: a fixed 14rem `aside`, a header with the workspace name, a tagline, and a Sign out button, and a bottom tab bar under `md`. The router is `<Routes>`, not a data router, so `useMatches` and route `handle` are not available.

Facts the plan rests on:

- `GET workspaces/<id>/reports/?triage_state=new` and `GET workspaces/<id>/follow-ups/?bucket=needs_approval` are paginated and return `count`. The inbox chips and the follow-up tabs already read counts this way.
- The member's name is in the session (`Session.user.full_name`, `email`), cached under `sessionQueryKey` by `RequireAuth`. The workspace context holds only the membership.
- `/dev/ui` renders AppShell with no `RequireAuth`, so it has no session and no workspace.
- E2e specs find Sign out with `getByRole('button', { name: 'Sign out' })` in six places: `accounts.spec.ts` (4), `themes.spec.ts` (1), `ui-foundation.spec.ts` (1). `ui-foundation.spec.ts` also finds the sidebar with `page.locator('aside')`.
- `motion.spec.ts` finds navigation links by exact name (`Problems`, `Follow-ups`). A count inside the link would change its name.
- The token parity test in `src/lib/theme.test.ts` reads only the first `:root {` block of `theme.css`. A block appended at the end does not affect it.
- `scripts/shots.mjs` does not use the navigation or Sign out. It needs no edit.

## Goals / Non-Goals

Goals: the four items in the issue, with the row height from #176 settled.

Non-goals: the command palette, a workspace switcher, a new API, any change to feature pages.

## Decisions

### D1. Registry components

From `frontend`, run `npx shadcn add sidebar dropdown-menu breadcrumb`. The sidebar item also brings `sheet`, `tooltip`, and `hooks/use-mobile.ts`. It lists `button`, `separator`, `input`, and `skeleton` as registry dependencies, and those exist: answer no to every overwrite prompt. After the run, `git status` must show only new files under `components/ui/` and `hooks/`, and no change to `package.json` or the lockfile. If either file changes, stop and ask.

### D2. Desktop only

The Sidebar uses `collapsible="icon"` and shows from `md` up. Under `md` the shell renders no sidebar and no trigger, so the shadcn mobile sheet never opens. The bottom tab bar stays as it is, with the name "Primary navigation".

### D3. Row height (#176)

Menu buttons keep `min-h-11` on desktop, in the expanded sidebar and in the rail. The shadcn default (`h-8`, and `size-8!` in the rail) is overridden by class on the shell's own usage, not by editing `sidebar.tsx`. The expanded width stays 14rem through `--sidebar-width`. The rail width is the row height plus the sidebar padding. Phone tab targets stay 44 px.

### D4. Collapse state

The shell controls `open` and saves it in `localStorage` under `rescribo-sidebar`, the same way `src/lib/theme.ts` saves the theme. With no saved value the sidebar is expanded. The line in `sidebar.tsx` that writes the `sidebar_state` cookie is removed: the app has no server rendering to read it, and a cookie would ride on every API request. This is the one edit to a registry file. Say so in the PR. The shadcn Ctrl/Cmd+B shortcut stays.

The toggle is the shadcn `SidebarTrigger` at the left of the header, desktop only.

### D5. Sidebar header and the workspace name

The sidebar header keeps the wordmark link to the inbox. The workspace name moves out of the header into the user menu trigger, under the member's name. The Demo badge stays in the header, after the breadcrumbs, at every width, with the label "Demo workspace". That keeps the demo-workspace requirement "every screen shows a demo label" true on phones and with the rail collapsed.

In the rail the wordmark link is hidden: no compact mark exists and the wordmark is wider than the rail. The Inbox destination is the row below it. The spec delta modifies "Wordmark returns to the inbox" to say the wordmark shows in the expanded sidebar.

### D6. User menu

One `UserMenu` component in `layout/`, built on `DropdownMenu`. Content:

- a label with the member's full name and email;
- a "Theme" radio group with Light, Dark, and System, bound to `useThemePreference`. Options come from `[...THEMES, 'system']` in `src/lib/theme.ts`, so a later theme shows up without an edit here;
- a separator and Sign out.

In a demo workspace the label area also shows `demoDescription`, under the email. The header keeps only the Demo badge.

The trigger in the sidebar footer shows an `Avatar` with initials, the name, and the workspace name. In the rail it shows the avatar only, with the name as its accessible name. The menu is a floating surface: `shadow-elevation-3`.

Under `md` the sidebar is not shown, so an avatar button at the right of the header opens the same `UserMenu`. It uses `touchTarget` and has the member's name as its accessible name. The bottom bar keeps four tabs.

The theme choice also stays under Settings, Appearance. `theme-settings.tsx` is not edited.

The shell reads the session with `useQuery({ queryKey: sessionQueryKey, queryFn: getSession, enabled: !isGallery })`. With no session data (the gallery) the user menu does not render, so the gallery still shows no Sign out.

Sign out keeps today's mutation. A failed sign-out keeps the `role="alert"` message in the header, because the menu has closed by then and toasts belong to #200.

### D7. Counts

`useNavigationCounts(workspaceId)` in `layout/` runs two queries:

- `reportKeys.list(workspaceId, { triage_state: 'new' })` with `listReports`;
- `followUpKeys.list(workspaceId, 'needs_approval', 1)` with `listFollowUps`.

Both use the existing key families, so every mutation that already invalidates `reportKeys.all` or `followUpKeys.all` refreshes the counts, and the follow-ups key is shared with the Needs approval tab. Each query refetches every 30 s (`NAV_COUNTS_REFRESH_MS` in the hook file). The queries are off when there is no workspace.

Each request returns a page of up to 25 rows to get one number. That is what the chips do today. A lighter count endpoint would be a backend change and is not part of this issue.

Display:

- The count is a `SidebarMenuBadge`, a sibling of the link, in Geist Mono. The link's accessible name stays "Inbox" or "Follow-ups".
- The badge has screen-reader text: "3 new reports", "2 follow-ups need approval".
- Zero, loading, and a failed request show no badge. The shell shows no error state for counts; the pages own those.
- Above 99 the badge reads "99+".
- In the rail and on the phone tab bar the same count sits on the corner of the icon.

### D8. Breadcrumbs

`Breadcrumbs` in `layout/` builds the trail from `useLocation().pathname` with `matchPath` against a small table in the same file. `App.tsx` is not edited.

| Path | Trail |
| --- | --- |
| `/inbox` | Inbox |
| `/inbox/new` | Inbox / New report |
| `/inbox/:reportId` | Inbox |
| `/problems` | Problems |
| `/problems/:problemId` | Problems / problem title |
| `/follow-ups`, `/follow-ups/:followUpId` | Follow-ups |
| `/follow-ups/:followUpId/page` | Follow-ups / report title |
| `/settings` | Settings |
| `/dev/ui` | UI gallery |

The last item is the current page: plain text with `aria-current="page"`. Earlier items are links. The two panel routes show only the section, because the list stays on screen and the panel has its own heading.

Titles come from the detail queries the pages already run: `problemKeys.detail` with `getProblem`, and `followUpKeys.detail` with `getFollowUp` (`report.title`). The same key means one request. While the title loads, or if the request fails, the item reads "Problem" or "Follow-up". Long titles truncate.

The "Back to follow-ups" link on the follow-up page stays. It restores the bucket and page; the breadcrumb link goes to the plain list.

### D9. Place for the command palette trigger

The header's right side keeps one container after the Demo badge. It holds the sign-out error and, on phones, the avatar trigger from D6. A one-line comment marks it as the place for the #199 trigger. Nothing is built for it.

### D10. Tokens

Append one block at the end of `frontend/src/styles/theme.css`, an `@theme inline` block of aliases:

| Token | Alias of |
| --- | --- |
| `--color-sidebar-foreground` | `--foreground` |
| `--color-sidebar-primary` | `--primary` |
| `--color-sidebar-primary-foreground` | `--primary-foreground` |
| `--color-sidebar-accent` | `--selected` |
| `--color-sidebar-accent-foreground` | `--foreground` |
| `--color-sidebar-border` | `--border` |
| `--color-sidebar-ring` | `--ring` |

`--color-sidebar` exists already. `--selected` is today's hover and active row colour, so the rows look the same. If `sidebar.tsx` reads a bare `var(--sidebar-*)` anywhere, add that alias in the same block's `:root` companion and nothing else. No other line of the file changes.

### D11. Skip link and landmarks

"Skip to main content" stays the first element in the document and the first Tab stop. `main` keeps `id="main-content"` and `tabIndex={-1}`. The sidebar's navigation is named "Primary navigation", the breadcrumb `nav` is named "Breadcrumb", and the phone tab bar keeps "Primary navigation" (only one of the two shows at a time). Axe must report no duplicate landmark.

### D12. DESIGN.md

Lines reworded, each listed in the PR body:

- Components: "AppShell: desktop sidebar, mobile bottom navigation, and a compact status header".
- Layout rules: "Desktop uses a sidebar, a flexible content area, and compact 44px navigation rows."
- Layout rules: "AppShell keeps Sign out in the header at every width. The sidebar has no sign-out block, and the UI gallery shows no Sign out."
- Themes: "Members pick a theme under Settings, Appearance." gains the user menu.
- Wordmark: "In the sidebar it links to the inbox." says the expanded sidebar.

One section is added at the end, "App shell": rail, row height, user menu, counts, breadcrumbs, and the place for the palette trigger. The shadcn primitives line gains the new components by appending to the list.

## Risks / Trade-offs

- The shadcn Sidebar reads `useIsMobile` through `matchMedia`, which jsdom lacks. Shell tests must stub it, as `theme.test.ts` does.
- A breadcrumb link named "Problems" is visible next to the sidebar link on a problem page. E2e locators that take the first match or run from another page are fine; a new strict locator on that page must scope to a landmark.
- `theme.css` and `DESIGN.md` are edited by #197 and others. The appended block and the added section keep merges simple. The three reworded DESIGN.md lines can conflict.
- Six e2e steps change. `accounts.spec.ts` belongs to #202, so only its four Sign out lines and the import change there.

## Open Questions

None. The answers in `.claude/answers/plan.md` settled them:

1. Phones: an avatar button at the right of the header under `md` opens the same `UserMenu`. The bottom bar keeps four tabs (D6).
2. Demo notice: the Demo badge stays in the header. The sentence shows inside the user menu in a demo workspace (D6).
3. Breadcrumbs on detail pages show the record title, from the detail query the page already runs (D8).
4. The theme choice sits beside Settings, Appearance. `theme-settings.tsx` is not edited (D6).
5. The wordmark link is hidden when the sidebar is collapsed. The spec delta modifies "Wordmark returns to the inbox" (D5).
6. E2e: `frontend/e2e/shell.ts` gets `signOut(page)`, used in the six places. `accounts.spec.ts` belongs to #202 in this batch: change only its four Sign out lines and the import.
