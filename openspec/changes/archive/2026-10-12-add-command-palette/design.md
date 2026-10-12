# Design

## Context

See `proposal.md` for the motivation. Facts the plan rests on:

- `GET workspaces/<id>/reports/?q=` matches the report title, description, or captured source text (`backend/feedback/inbox.py`). `GET workspaces/<id>/problems/?q=` matches the title or summary (`backend/feedback/problem_reads.py`). Both are workspace-scoped and return pages of 25 with no page-size parameter. So both can search by title, and both also return rows whose title does not contain the text.
- `listReports` and `listProblems` with `reportKeys.list` and `problemKeys.list` already wrap these endpoints in `frontend/src/api/`.
- `/inbox/:reportId` shows a report beside the list and `/problems/:problemId` shows a problem.
- The only keyboard handler in the app is the Cmd/Ctrl+B effect in `SidebarProvider` (`frontend/src/components/ui/sidebar.tsx`). `e2e/ui-foundation.spec.ts` uses it.
- `AppShell` holds the header, and marks the place for the trigger with a comment. `/dev/ui` renders `AppShell` with no session and no workspace.
- The shadcn `command` item needs `cmdk` and the registry items `dialog` and `input-group`. `input-group` lists `button`, `input`, and `textarea`, which exist. `dialog` lists `button`. `cmdk` 1.1.1 accepts React 19.
- `frontend/src/styles/theme.css` is not in this issue's paths. Restyling happens through classes in the new `ui/` files.
- `THEMES` in `frontend/src/lib/theme.ts` is the list of themes. The user menu builds its choices from `[...THEMES, 'system']`.

## Goals / Non-Goals

**Goals:** the palette, its trigger, the two primitives, and the shortcut registry.

**Non-Goals:** pickers, `Popover`, toasts (#200); the GitHub issue preview (#208); anything under `frontend/src/features/follow-ups/` (#209); new theme palettes (#203); any backend or API change; recent items, fuzzy ranking, or follow-up search.

## Decisions

### D1. Registry components

From `frontend`, run `npx shadcn add command dialog`. It adds `command.tsx`, `dialog.tsx`, and `input-group.tsx` under `components/ui/`, and `cmdk` to `package.json`. Answer no to every overwrite prompt. After the run `git status` must show those three new files, and `git diff frontend/package.json` must show one added line, `cmdk`. Any other change to `package.json`, or a changed existing `ui/` file: stop and ask.

`input-group.tsx` stays as the registry ships it, so `command.tsx` keeps matching the registry. Alternative: strip `InputGroup` out of `CommandInput`. Rejected: it forks the primitive that #200 reuses.

### D2. Token styling

Edit only the three new files. `Command` stays generic: no palette wording, no routing, no data.

- Surfaces: `bg-popover`, `shadow-elevation-3`, no border (DESIGN.md, Elevation level 3). Radius is `rounded-card` on the dialog and `rounded-control` on items. Replace every `rounded-xl!`, `ring-*` edge, and raw colour the registry ships with a token class.
- Overlay: the `Sheet` overlay classes, so the two overlays match.
- Motion: fade plus a small scale on open, `--duration-base`, `--ease-out-soft`. Every animation class carries `motion-safe:`, so reduced motion gets none.
- Items: `min-h-9` on desktop and `touchTarget` on phone. The input is 44px on phone.
- Shortcut hints use `CommandShortcut` in Geist Mono (DESIGN.md, Tokens).

### D3. Shortcut registry

`frontend/src/lib/shortcuts.ts`, hand-rolled, no library. Two shortcuts, each a modifier plus one key, need about 50 lines. `tinykeys` and `react-hotkeys-hook` earn their place with sequences, scopes, or many bindings; none exist yet. The module is the boundary, so a library can replace its inside later without touching callers.

- `SHORTCUTS`: one record, the only place a shortcut is declared. `openPalette: { key: 'k', label: 'Open command palette' }` and `toggleSidebar: { key: 'b', label: 'Toggle sidebar' }`. Every shortcut is Cmd or Ctrl plus `key`.
- `useShortcut(id, handler)`: binds the handler for `id` while the component is mounted. Binding an `id` that is already bound throws.
- One `keydown` listener on `window`, installed with the first binding. It matches `metaKey || ctrlKey`, no Alt, no Shift, and `event.key.toLowerCase()`. It calls `preventDefault` only when a handler is bound. It does not skip text fields: both shortcuts carry a modifier.
- `runShortcut(id)` calls the bound handler. `boundShortcuts()` returns the bound ids with their labels, for the palette list.
- `shortcutKeys(id)` returns `['⌘', 'K']` on Apple devices and `['Ctrl', 'K']` elsewhere, from `navigator.platform`.

`sidebar.tsx` loses its `useEffect` and `SIDEBAR_KEYBOARD_SHORTCUT`. `ShellContents` in `app-shell.tsx` calls `useShortcut('toggleSidebar', toggleSidebar)`. Behaviour is unchanged: both Cmd+B and Ctrl+B toggle on every platform.

### D4. Palette structure

`frontend/src/components/command-palette/`:

- `command-palette.tsx`: the dialog and its groups. Props: `open`, `onOpenChange`, `workspaceId`.
- `palette-trigger.tsx`: the header button.
- `use-palette-search.ts`: the two queries.

`ShellContents` owns the `open` state, binds `useShortcut('openPalette', toggle)`, and renders the trigger and the palette where the comment is. Neither renders on `/dev/ui` or without a workspace. The palette is a shell component, not a feature: it holds no product workflow, only navigation, the theme, and links to records.

Groups, in order: Go to, Reports, Problems, Theme, Shortcuts. Each item closes the palette after it runs.

### D5. Screens

Move the four navigation items out of `Navigation` into `frontend/src/components/layout/navigation-items.ts` (label, path, icon), so the sidebar, the tab bar, and the palette read one list. Counts stay in `Navigation`. This step is a refactor with no behaviour change and gets its own commit-sized task. The palette adds one screen of its own, "New report" at `/inbox/new`, with the label the breadcrumb already uses.

### D6. Search

`use-palette-search.ts` runs `listReports(workspaceId, { q })` and `listProblems(workspaceId, { q })` with the existing `reportKeys.list` and `problemKeys.list` keys, so a triage or edit invalidates palette results like any list. The text is trimmed and debounced by 200ms. Queries are enabled at two characters or more. Each group shows the first five rows of the first page.

`Command` gets `shouldFilter={false}`. cmdk's own filter would hide server rows that matched on description or summary, so the palette filters its static items itself: case-insensitive substring on the label. Server rows show as returned.

A report row shows the title and the customer label. A problem row shows the title. Neither shows a status: a status needs `StatusBadge` and a tone map that live in the features, and the palette's job is to get there. A report goes to `/inbox/<id>`, a problem to `/problems/<id>`.

States, per group, as items inside the list: "Searching…" while pending, and "Reports could not be searched. Retry" (or Problems) on error, where choosing the item refetches that query only and keeps the palette open. `CommandEmpty` reads "No results" when no item at all is shown and no search is pending.

### D7. Theme

A Theme group with one item for each of `[...THEMES, 'system']`, labelled "Light theme", "Dark theme", "System theme", bound to `useThemePreference`. The current one has a check icon and the visually hidden text "current". #203 adds palettes by extending `THEMES`; nothing here changes then.

### D8. Shortcuts group

Built from `boundShortcuts()`, each item with its label and `shortcutKeys`. Choosing one calls `runShortcut`. "Open command palette" therefore closes the palette, which is what its keys do while it is open. The group is hidden under `md` with `useIsMobile`: phones have no keys to show, and the sidebar toggle does nothing there.

### D9. Trigger

In the header's right group, before the sign-out alert and the phone user menu. Desktop: an outline `Button` reading "Search" with a search icon and the keys from `shortcutKeys('openPalette')` in a `kbd`. Phone: the icon alone at 44px with `touchTarget`. Its accessible name is "Open command palette" at both widths, with `aria-keyshortcuts="Meta+K Control+K"`. The dialog title is "Command palette", visually hidden.

### D10. Gallery and docs

`ui-gallery.tsx` gets a "Command" card with a static inline `Command` (two groups, one shortcut hint) and a button that opens a `Dialog`, so both primitives can be seen without a workspace.

`frontend/DESIGN.md` gets one new section at the end, "Command palette": the trigger and keys, the group order, the registry as the only place for shortcuts, and that `Command`, `Dialog`, and `InputGroup` are shared primitives. No existing line is reworded. That leaves one stale sentence in "App shell" ("The header keeps an empty place for the command palette trigger.") and a primitives list that omits the new ones; question 4 in the plan summary covers both.

### D11. Screenshots

`scripts/shots.mjs` is not edited: it waits on no landmark this change renames. The implementer adds a helper in the git-ignored `.claude/shots/` for the open palette, as #198 did for the user menu.

### Built differently

- `input-group.tsx` is the registry file run through the repo's Prettier config and nothing else.
- `CommandDialog` takes an `onCloseAutoFocus` prop. Radix restores focus only to its own `DialogTrigger`, and the palette opens from a key as well. The palette remembers the focused element on open and puts focus back on close.
- The registry's `CommandDialog` does not wrap its children in `Command`, so the palette wraps its own `Command` with `shouldFilter={false}`.
- Report and problem searches use `retry: false` so a failure shows its retry item at once.
- The phone width e2e check compares `scrollWidth` with `clientWidth` before the palette opens, and with `innerWidth` while it is open: the dialog's scroll lock pads the page for the scrollbar it removes.

## Risks / Trade-offs

- [Body matches look wrong in a "find by title" list] → The spec ties the palette to the same matches as the two page searches, so the three agree. Question 1 asks the maintainer to confirm.
- [The newest 25 matches hide an older title match] → Same limit as page one of the inbox search. Typing more narrows it.
- [`cmdk` brings its own `@radix-ui/*` packages beside the `radix-ui` umbrella] → Lockfile grows; the palette uses the app's `Dialog`, not cmdk's. Check the build size in the PR.
- [Ctrl+K is a browser shortcut in Firefox] → `preventDefault` on `keydown` takes it, as it does for Ctrl+B today.
- [`package.json` conflicts with #208] → One added line. Whoever merges second rebases the lockfile.
- [A new visible button fails the phone touch-target sweep in `ui-foundation.spec.ts`] → The trigger carries `touchTarget`; task 4.2 runs that spec.

## Open Questions

None that can wait. The questions for the coordinator are in the plan summary and change the specs if answered differently.
