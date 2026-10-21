# Tasks

## 1. Sections and routes

- [x] 1.1 Add `frontend/src/features/settings/sections.ts` with the ordered sections (slug, label, ownerOnly) and a helper that filters them by role; verify with a unit test that a non-owner gets Appearance, Connections, and Slack account only.
- [x] 1.2 Turn `settings-page.tsx` into the settings layout (header, section nav, `Outlet`, the `key={workspace.id}` reset) and split its body into one component per section: Appearance (renders `ThemeSettings` unchanged), Members, Connections (owns the connections query, the demo alert, and the cards), Slack account, Workspace (deletion). Each section sets `PageTitle` to "<Section> · Settings". Verify `settings-page.test.tsx` passes after its renders point at the right section URL.
- [x] 1.3 Gate Members and Workspace on the owner role inside the section, showing the existing owner note otherwise; verify with unit tests that a member opening `/settings/members` and `/settings/workspace` sees the note and no member, invitation, or delete control.
- [x] 1.4 Replace the flat `settings` route in `App.tsx` with the nested routes and an index redirect to `appearance`; verify with a unit test that `/settings` lands on `/settings/appearance` and each section URL renders its section.
- [x] 1.5 Build the section nav (`<nav aria-label="Settings sections">`, `NavLink` list, side column from `md`, scrolling row with `touchTarget` links below `md`, current link scrolled into view); verify with a unit test that the current link has `aria-current="page"` and a member's nav lists three sections.

## 2. Readable connection facts

- [x] 2.1 Rewrite the facts `dl` in `connection-settings.tsx` with the terms and values in design.md ("Slack workspace", "GitHub account", "Repository" with "Private" or "Public", "Last reached Slack/GitHub", "Issues last synced", "Not yet"); remove scopes and `external_id` from it. Verify with unit tests for the "Connected Slack", "Never reached", and "Repository in plain words" scenarios.
- [x] 2.2 Add the owner-only `<details>` "Technical details" with Provider ID, Scopes, Last API success, Last issue sync (GitHub), and Error code when set, empty values reading "None"; verify with unit tests that it is collapsed, that expanding it shows the team ID and scopes, and that a member gets no disclosure.
- [x] 2.3 Reword `slack-account.tsx` to "Your Slack account is linked." with the link date, and move the user and team IDs into an owner-only "Technical details" disclosure; verify with unit tests for both "Readable Slack account link" scenarios.

## 3. Links and breadcrumbs (shared files, after coordinator approval)

- [x] 3.1 Point the "Open settings" link in `release-picker.tsx` and the link in `github-issue-create.tsx` at `/settings/connections`; verify their existing unit tests pass with the new href asserted.
- [x] 3.2 Change `CallbackView` in `backend/connections/views.py` to redirect to `/settings/connections`; verify with a backend test that a successful callback redirects there.
- [x] 3.3 Teach `breadcrumbs.tsx` the settings sections: "Settings" as a link to `/settings`, then the section label from `sections.ts`; verify with a case in `breadcrumbs.test.tsx` for `/settings/connections`.
- [x] 3.4 Add a short settings note to `frontend/DESIGN.md` under "Follow-ups and settings": sections with their own URLs, the section nav, plain fact terms, owner-only "Technical details" as `<details>`. Add text only; do not reword existing lines.

## 4. End-to-end and screenshots

- [x] 4.1 Update `frontend/e2e/settings.spec.ts`: owner flows go to `/settings/members` and `/settings/workspace`; the member checks the nav lists three sections and that `/settings/workspace` shows the owner note; add the section nav at 390px and 320px with no horizontal scroll and every section reachable; keep the axe and touch-target checks on each visited section.
- [x] 4.2 Point `frontend/e2e/demo.spec.ts` at `/settings/connections` for the demo alert check and `/settings/workspace` for the absent delete button, and `frontend/e2e/ui-foundation.spec.ts` "sign out is in view on settings" at `/settings/members`; verify both specs pass.
- [x] 4.3 In `.claude/skills/work-issues/scripts/shots.mjs`, replace the single `/settings` shot with one shot per section the demo visitor sees (`settings-appearance`, `settings-connections`, `settings-slack-account`); verify the script runs to completion against the dev servers.

## 5. Repository checks

- [x] 5.1 Run `npx @fission-ai/openspec validate --all --strict` and verify it passes.
- [x] 5.2 With PostgreSQL and Redis running, run `task check test build schema-check` and verify every task passes.
- [x] 5.3 Run `RESCRIBO_E2E_API_PORT=8201 RESCRIBO_E2E_FRONTEND_PORT=5201 task e2e` and verify it passes.
- [x] 5.4 Take the after shots and build `.claude/shots/compare.html` with `compare.py`.

## Workflow follow-up

- Archive the change in the PR that completes it.
