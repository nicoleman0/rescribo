# Design

## Context

`follow-up-detail.tsx` exports `FollowUpDetailPanel`. It owns the detail query (retry rules for 403 and 404, 5s polling while a send is queued or in progress), the loading, not found, access removed, and error states, and `FollowUpBody`. `FollowUpBody` renders the summary, message section, customer contact, recipient form (owners), and history, with a `Separator` between each. Each section is a bordered box (`rounded-card border border-border p-4`) inside the raised panel. The title is an `h2`, section headings are `h3`, and History is an `h2`.

`follow-ups-page.tsx` renders the list and, when `:followUpId` is set, the panel in an unkeyed `animate-panel-enter` slot with `key={followUpId}` on the panel. The panel's back link keeps the list's query string.

`ProblemDetailPage` is the existing full-page detail: `animate-page-enter`, `max-w-5xl`, a ghost "Back to problems" link, an `h1` title, and a two-column grid at `lg` with `shadow-elevation-1` cards (`problemCard`).

## Goals / Non-Goals

**Goals:**
- One detail component for both views. No copied query, state handling, section, or mutation.
- The panel looks and behaves as today, apart from the new link and the History heading level.

**Non-Goals:**
- Changing the list, the bucket tabs, or list row targets.
- Cross-screen width and alignment (#99). The page uses the shell's content width.
- A full page for reports, or changes to the problems screens (#103, #122).

## Decisions

### One shared content component

Split `FollowUpDetailPanel` into:

- `FollowUpDetailContent({ workspaceId, followUpId, layout })`: the current query, the async states, and `ReadyState` around `FollowUpBody`. `layout` is `'panel' | 'page'`.
- `FollowUpDetailPanel`: the raised `section aria-label="Follow-up detail"`, a header row with "Back to follow-ups" and "Open full page", and `FollowUpDetailContent layout="panel"`.
- `FollowUpDetailPage` in a new `follow-up-detail-page.tsx`: reads `:followUpId` and the active workspace, renders the page root and "Back to follow-ups", and `FollowUpDetailContent layout="page" key={followUpId}`.

`FollowUpBody` passes `layout` to the parts that differ through a small React context in `follow-up-detail.tsx`, so the eight section components do not each grow a prop. Only two things read it: the section box class and the heading level. Alternative considered: a second body component for the page. Rejected because it would duplicate the section order and the owner and notification conditions.

### Page layout

- Root: `animate-page-enter grid max-w-5xl gap-6`, like the problem page.
- Header, full width: statuses, the title as `h1` with the version, and the details `dl`.
- From `lg`: a main column with Message and Customer contact, and a 20rem side column with Recipient (owners) and History.
- Below `lg`: one column in the panel's order: header, message, contact, recipient, history. The DOM order is the phone order, so no grid placement tricks are needed.
- No `Separator`s on the page; card gaps separate sections.

### Section surfaces

In the panel, sections stay bordered boxes inside the raised surface. On the page, sections rest on the page background, so they use the resting card style that DESIGN.md gives side-column cards: card radius, `bg-card`, `shadow-elevation-1`. The recommended source is the existing `problemCard` class from `features/problems/problem-card.ts`, imported read-only, so the rule keeps one home and no problems file changes.

### Headings

Page: title `h1`, section headings `h2`. Panel: title `h2`, section headings `h3`. History moves from `h2` to the section level in both views; in the panel that fixes a sibling heading at the wrong level. A small `SectionHeading` in `follow-up-detail.tsx` picks the level from the layout context.

### Links and query string

- Panel "Open full page": `/follow-ups/:id/page` plus the current query string, ghost small button with a `Maximize2` icon, right side of the panel header row.
- Page "Back to follow-ups": `/follow-ups` plus the query string, so bucket and page survive. Opened by a bare URL, it goes to `/follow-ups`.

### Route

Add `follow-ups/:followUpId/page` to `App.tsx` with `FollowUpDetailPage`, after the two existing follow-up routes. It has one more segment than `follow-ups/:followUpId`, so the list route still matches `/follow-ups/:id`.

## Risks / Trade-offs

- [Panel regressions from the split] → Existing `follow-up-detail.test.tsx` tests keep rendering `FollowUpDetailPanel`, and `motion.spec.ts` keeps checking the unkeyed panel slot.
- [Importing a problems constant into follow-ups couples two features] → It is read-only and #99 can move it to a shared home. The alternative is a local copy of the same rule.
