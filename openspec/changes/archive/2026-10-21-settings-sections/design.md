# Design

## Context

`SettingsPage` renders every part of settings in one column and owns the connections query, which both the connection cards and `SlackAccount` read. `App.tsx` has one flat `settings` route. `Breadcrumbs` matches `/settings` with `end: true`, so a sub-route would lose its trail. The OAuth `CallbackView` redirects to `/settings`. `ConnectionSettings` renders a `dl` with Identity (plus `external_id` in mono), Repository, Scopes, Last API success, and Last issue sync.

## Goals / Non-Goals

**Goals:**
- One list of sections that the nav, the routes, and the breadcrumb all read.
- Each section component works on its own, so a section can move or change without touching the others.

**Non-Goals:**
- Adding settings sections to the command palette. It keeps its single "Settings" entry, which lands on Appearance.
- Relative times ("5 minutes ago"). Times keep the existing `formatDate` output.
- Changes to `ThemeSettings`, `AllowedChannels`, the confirm step, or any request a card sends.

## Decisions

**Nested routes with a layout.** `App.tsx` gets `settings` as a parent route whose element is a settings layout (header, nav, `Outlet`), an index route that redirects to `appearance`, and one child route per section. An unknown `/settings/<x>` falls through to the existing "Page not found". Alternative: one `settings/:section` route with a switch. Rejected: explicit routes keep the router as the only place a URL maps to a component.

**One sections list.** A `sections.ts` module in `features/settings` exports the ordered list of `{ slug, label, ownerOnly }`. The nav filters it by role. The breadcrumb looks up the label by slug. The layout keeps the `key={workspace.id}` reset that `SettingsPage` has today, so switching workspace clears section state.

**Owner gate per section.** Members and Workspace render the owner note when the role is not owner. The nav hides them, but the gate lives in the section so a direct link is covered. The API already refuses non-owner writes; this is presentation.

**Connections query in each section that needs it.** Connections and Slack account each call `useQuery` with the existing `[...settingsKey(id), 'connections']` key. TanStack Query shares the cache, so moving between them does not refetch twice. Alternative: lift the query into the layout and pass it down. Rejected: Appearance, Members, and Workspace would poll connections every 30 seconds for nothing.

**Nav markup.** A `<nav aria-label="Settings sections">` with a list of `NavLink`s, which set `aria-current="page"`. From `md` up (the shell's phone/desktop split) it is a narrow column beside the section. Below `md` the same list is a single row that scrolls inside itself (`overflow-x-auto`), with links sized by `touchTarget`, and the current link scrolled into view on load. One component, two layouts by CSS, so the list cannot drift. Alternative: a `NativeSelect` on phones. Rejected: a select hides the other sections and needs a second control.

**Page title.** Each section sets `PageTitle` to "<Section> · Settings", giving "Connections · Settings · Rescribo". The layout keeps the "Settings" `h1` and workspace name; each section's own heading is an `h2`.

**Plain facts stay a `dl`.** DESIGN.md says detail facts use a `dl` with a fixed term column, so the fix is the terms and values, not the layout. Slack: "Slack workspace", "Last reached Slack". GitHub: "GitHub account", "Repository" (name, then "Private" or "Public" in words), "Last reached GitHub", "Issues last synced". A null time reads "Not yet". Job counts and the error detail stay as they are; the spec already requires them.

**Technical details as native `<details>`.** Owners get `<details>` with a `<summary>` "Technical details" below the facts, holding a second `dl`: Provider ID (`external_id`), Scopes (comma list), Last API success, Last issue sync (GitHub), and Error code when set; empty values read "None". `problem-activity.tsx` already uses `<details>`, and it needs no new component and is keyboard and screen-reader accessible as is. Alternative: a shadcn Collapsible. Rejected: a new primitive for one disclosure.

**Slack account wording.** "Linked to Slack user U… in team T…" becomes "Your Slack account is linked." with the link date. The Slack user and team IDs move into a "Technical details" disclosure shown to owners only, the same rule as the connection cards.

**Links.** `release-picker.tsx` and `github-issue-create.tsx` link to `/settings/connections`. `CallbackView` redirects to `/settings/connections`. The sidebar entry stays `/settings`; `NavLink` matches child paths, so it stays marked on every section.

## Risks / Trade-offs

- [Shared e2e files assume one page] `demo.spec.ts` looks for the demo alert and the absent delete button on `/settings`; `ui-foundation.spec.ts` waits for the "Members and invitations" heading on `/settings`. → Point each at the section that holds what it checks.
- [Before and after shots differ in shape] `shots.mjs` captures only `/settings`, which will now show Appearance. → Add one shot per section the demo visitor can see, so the comparison shows Connections.
- [Parallel edits] #203 edits `theme-settings.tsx`, #200 may edit `allowed-channels.tsx`. → This change only imports them.
- [Horizontal scroll row on phones] A scrolling row can hide a section off screen. → Five short labels; the current link is scrolled into view, and the e2e checks each section is reachable at 320px.
