# Proposal

## Why

Delivers GitHub issue #236. The shared empty state titles itself with an `h1`. On a list page, and in a detail panel beside a list, the page already has its own `h1`, so screen reader users hear a second level-1 heading that reads as a new page. Where the empty state is the whole page, such as the not-found route, it must keep the `h1` or the page has none.

## What Changes

- The empty state title is a level-2 heading by default.
- Whole-page uses ask for a level-1 title: the not-found route, "Workspace access removed", the problem detail page's not-found and access-removed states, and the follow-up full page's not-found and access-removed states.
- The follow-up detail view picks the level from its layout: level 1 as a full page, level 2 as a panel. This matches the follow-up title rule already in place.
- List page empty states (Inbox, Problems, Follow-ups) and the inbox report panel's not-found and access-removed states use the default level 2.
- Page tests assert that each of these pages has exactly one level-1 heading.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a requirement that empty, not-found, and access-removed states keep each page to one level-1 heading.

## Impact

- `frontend/src/components/states/async-states.tsx` (`EmptyState`, and `QueryState` through it).
- Call sites in `frontend/src/App.tsx`, `frontend/src/components/auth/require-auth.tsx`, and `frontend/src/features/` (inbox, problems, follow-ups).
- Tests beside those files. No API, schema, or visual change.
