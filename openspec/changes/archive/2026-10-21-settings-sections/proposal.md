# Proposal

Delivers GitHub issue #201.

## Why

Settings is one long page: appearance, members, connections, the Slack account, and deletion follow each other with no navigation, and no link can open one part. Connection cards show raw values such as "Scopes: None" and "Last API success: Never", which most members cannot read.

## What Changes

- Settings splits into five sections, each at its own URL: `/settings/appearance`, `/settings/members`, `/settings/connections`, `/settings/slack-account`, and `/settings/workspace`. `/settings` redirects to Appearance.
- A section nav shows one section at a time: a side nav at desktop width, a compact top nav on phones. The current section is marked.
- Members and Workspace (deletion) are owner-only. They are not in a non-owner's nav. A direct link to one shows the existing "Workspace owners manage..." note and no controls.
- The demo alert about disabled integrations moves to the Connections section.
- Connection cards state their facts in plain words for everyone: the connected Slack workspace or GitHub account, the repository and its visibility, when Rescribo last reached the provider, and when GitHub issues last synced. A missing time reads "Not yet".
- Owners also get a collapsed "Technical details" disclosure on each card with the raw values: provider ID, scopes, last API success, last issue sync, and error code. Members do not see it.
- The Slack account section says in plain words that the account is linked and since when. The Slack user and team IDs move into the same owner-only disclosure.
- The breadcrumb on a section shows "Settings" as a link followed by the section name.
- Links that point at `/settings` to fix a connection now open `/settings/connections`: the release picker, the GitHub issue form, and the redirect after a provider setup callback.
- No change to what a connection does, to the API, or to `ThemeSettings`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds requirements for settings sections, owner-only sections, and readable connection facts with owner technical details; adds a breadcrumb scenario for settings sections. The "Integration status cards" requirement is unchanged and still holds.

## Impact

- Frontend, owned: `frontend/src/features/settings/` (new section layout, nav, and section components; `settings-page.tsx` split; `connection-settings.tsx` facts), `frontend/src/App.tsx` (nested settings routes), `frontend/e2e/settings.spec.ts`.
- Frontend, shared (coordinator approval needed): `frontend/src/components/layout/breadcrumbs.tsx` and its test, `frontend/src/features/problems/release-picker.tsx`, `frontend/src/features/problems/github-issue-create.tsx`, `frontend/e2e/demo.spec.ts`, `frontend/e2e/ui-foundation.spec.ts`, `frontend/DESIGN.md` (settings notes), `.claude/skills/work-issues/scripts/shots.mjs` (one shot per section).
- Backend, shared: `backend/connections/views.py` `CallbackView` redirects to `/settings/connections`.
- No API, schema, or migration change.
- Parallel work: #203 edits `theme-settings.tsx`; #200 may edit `allowed-channels.tsx`. This change edits neither.
