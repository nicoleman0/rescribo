# Proposal

## Why

Issue [#102](https://github.com/nicoleman0/rescribo/issues/102): a follow-up opens only as a 24rem side panel beside the list. The message, customer contact, recipient, and history stack in that narrow column and compete for space with the list. A member cannot link to one follow-up without the list around it.

## What Changes

- Add a full page for one follow-up at `/follow-ups/:followUpId/page`. It opens by URL and from an "Open full page" link in the side panel header.
- `/follow-ups/:followUpId` stays the list with the side panel. List rows open the panel as today.
- The full page shows the same content and actions as the panel: statuses, details, message and its delivery actions, customer contact and outcome forms, recipient change for owners, and history. Wide screens use two columns; phones use one column in the panel's order.
- The page has a "Back to follow-ups" link that returns to the list with the bucket and page the member came from.
- Loading, not found, access removed, and load errors read the same as in the panel.
- Queued and in-progress sends refresh on the full page as they do in the panel.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds a requirement for the follow-up full page.

## Impact

Frontend only: `src/features/follow-ups/`, the follow-up routes in `src/App.tsx`, `e2e/follow-ups.spec.ts`, and an appended section in `frontend/DESIGN.md`. No API, database, or worker changes. The panel and the page share one detail component, its query, and its mutations. Shared motion and surface utilities from #106 are reused unchanged.
