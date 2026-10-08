# Design

## Context

The inbox lives in `frontend/src/features/inbox/`. Filters are URL search params read by `queryFromParams`; the list and the report panel are TanStack Query screens. The app shell centres content at `max-w-5xl` and the window scrolls, so there is no inner scroll container. At desktop the root font size is 13px, so the content column is about 830px and the current report panel (`22rem`) leaves the list about 530px wide.

The follow-ups page already shows bucket chips with counts from one list query per bucket. #109 owns that page, so the inbox gets its own chips rather than a shared component.

## Goals / Non-Goals

**Goals:**
- Port the mockup's inbox layout onto the existing tokens, `StatusBadge`, `Button`, and `NativeSelect`.
- Keep every filter, triage action, URL shape, and e2e flow working.

**Non-Goals:**
- Suggested problem UI, a placeholder for it, or calls to suggestion APIs. Left to #21.
- Motion (#106), shared components, the shell, or other screens.
- API changes. The counts reuse the list endpoint.

## Decisions

### Counts from list queries

Each chip runs the list query with the active filters, its own `triage_state`, and no page. The response `count` is the chip number. The chip whose state matches the URL shares its cache entry with the visible list, so that chip costs no extra request. Counts poll on the same 30-second interval as the list.

Alternative: a counts endpoint grouped by triage state. Cheaper per load, but it is an API change, which this milestone avoids unless required.

A chip whose count fails shows a marker with an accessible "count unavailable" label, and one retry button appears beside the chips. An invalid-filter (400) response is left to the list's existing "These filters are not valid" state.

### One row, two densities

The list is a CSS container. Above about 540px a row is a grid: a fixed-width badge column, the title (with the linked problem in muted text after it), the customer, an assignee avatar, and a short date. Below that width, which covers both an open report on desktop and phone width, the row drops to the badge, the title, a second line with customer and date, and the avatar. A container query, not a viewport breakpoint, because the list width depends on whether a report is open.

The source kind leaves the row. It stays in the Source filter and in the report panel. The avatar is decorative; the assignee name is in screen-reader text. The full date stays in the `time` element's `dateTime` and `title`.

### Filters behind one button on phones

The search form keeps report search, customer search, and the Search button. Below the `md` breakpoint the customer field and the row of chips and selects are hidden until the Filters button opens them. The button carries `aria-expanded`, `aria-controls`, and the number of active filters other than the report search. Above `md` the button is hidden and everything shows. The select labels become screen-reader only and the empty options name the filter ("Any assignee", "All sources"), so the controls fit on one row.

### Report panel

The panel keeps `shadow-elevation-2` and widens to `26rem`. On `lg` it is sticky below the top of the window and scrolls inside itself when taller than the viewport. "Back to reports" stays a link with the same name; on `lg` it renders as a close icon in the panel's corner. Inside the panel the order becomes: status, version and date; title and description; triage (grouping actions, then assignee); details; source; delete. Grouping is the usual next step for a new report, so it comes first.

## Risks / Trade-offs

- [Four list requests per filter change instead of one] → Each is a page of at most 25 rows on an indexed query, and one of them is the visible list. Revisit with a counts endpoint if the inbox grows past that.
- [A sticky panel with its own scroll can hide content below the fold] → The panel's max height is the viewport, so its scroll bar shows when content overflows.
- [Hidden labels on the filter selects] → The labels stay in the accessibility tree, and each select's empty option names the filter.
