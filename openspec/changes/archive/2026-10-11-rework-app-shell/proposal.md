# Proposal

Delivers GitHub issue #198, Rework the app shell: sidebar, user menu, and breadcrumbs (milestone H. Product-grade UI). The PR also closes #176.

## Why

The shell is four links in an empty sidebar and a header with a tagline and a bare Sign out button. It has no user menu, no counts on the navigation, and nothing that shows where a detail page sits.

## What Changes

- The desktop sidebar becomes the shadcn Sidebar. A member can collapse it to an icon rail and expand it again. The choice is kept in the browser.
- A user menu sits at the foot of the sidebar. It shows the member's name and email, the theme choice, and Sign out.
- Inbox shows the number of new reports. Follow-ups shows the number that need approval. Both read the existing list endpoints.
- The header shows breadcrumbs in place of the tagline. The workspace name moves to the user menu trigger. The Demo badge stays in the header at every width. In a demo workspace the "Fictitious data" sentence moves into the user menu.
- Sign out leaves the header and lives in the user menu.
- Desktop sidebar rows keep today's height (`min-h-11`, 35.75 px at the 13 px root). `frontend/DESIGN.md` is corrected to say so (#176).
- Phones keep the bottom tab bar. The sidebar and rail are desktop only. On phones an avatar button in the header opens the user menu.
- The wordmark link is hidden while the sidebar is collapsed.

Not in this change:

- The command palette and its trigger (#199). The header keeps a marked place for the trigger.
- Settings sections (#201), toasts and popovers (#200), colour palettes (#203).
- No backend change, no API contract change, no new route.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds requirements for the collapsible sidebar, the user menu, navigation counts, and breadcrumbs. Modifies "Wordmark returns to the inbox": the wordmark shows in the expanded sidebar only.

## Impact

- `frontend/src/components/layout/`: `app-shell.tsx` is rebuilt on the shadcn parts. New files for the user menu, the breadcrumbs, and the navigation counts, with tests.
- New shadcn files from the registry: `sidebar.tsx`, `sheet.tsx`, `tooltip.tsx`, `dropdown-menu.tsx`, `breadcrumb.tsx` in `frontend/src/components/ui/`, and `frontend/src/hooks/use-mobile.ts`. Existing files in `components/ui/` are not overwritten.
- `frontend/src/styles/theme.css`: one block appended for the sidebar colour aliases. No new colour values.
- `frontend/DESIGN.md`: five lines corrected (design.md, D12), one section added.
- `frontend/e2e/`: the Sign out step in `accounts.spec.ts`, `themes.spec.ts`, and `ui-foundation.spec.ts` changes, because Sign out is now a menu item. A new `frontend/e2e/shell.ts` holds the `signOut(page)` helper. `accounts.spec.ts` belongs to #202: only its four Sign out lines and the import change.
- No new npm dependency is expected: the registry items need `radix-ui`, `class-variance-authority`, and `lucide-react`, which are installed.
