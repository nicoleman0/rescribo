# Design

## Context

`ProblemList` in `problems-page.tsx` renders each row's first line as a `flex items-start justify-between gap-3` span. Its children are the title (`min-w-0 font-medium break-words`) and the badge group (`flex shrink-0 flex-wrap justify-end gap-1`). The group cannot shrink, so the title gets what is left. At 390px that is close to zero. `overflow-hidden` on the list clips a group wider than the row.

The `z-product-states` e2e test missed this. It checks document overflow, and the clipping happens inside the list.

## Goals / Non-Goals

**Goals:**
- Titles stay readable at 320px and 390px with every badge present.
- Desktop rows do not change visibly.

**Non-Goals:**
- Badge order, badge content, and the GitHub chip markup.
- The summary and owner lines of the row.
- `stagger-rows`, `ReadyState`, and the other motion utilities stay as they are.

## Decisions

**Intrinsic wrapping instead of a breakpoint.** The row becomes a wrapping flex line. The title is `grow basis-48` (flex-basis 12rem, which scales with the root font size: 13px on desktop, 15px below 768px). The badge group drops `shrink-0`. A flex line takes items while their bases fit, so the title never shares a line at less than 12rem. When the badges do not fit, they move to the next line and shrink to its width, and their own `flex-wrap` wraps them.

Alternatives:
- Stack below `sm` with viewport classes (`flex-col sm:flex-row`). The list width depends on the sidebar, not only the viewport, so between 768px and about 900px the title would still be squeezed.
- Stack with a container query on the list, as the inbox does (`@container`, `@xl:flex-row`). Every row then has the same layout at a given width, but it adds a breakpoint to tune. Intrinsic wrapping has no breakpoint and keeps short rows on one line.

Checked in the browser by applying the equivalent inline styles to the seeded demo before planning. At 390px the seeded row's title is 330px wide (it was 0) and the badges stay inside the row. At 320px every title is at least 194px wide. At 768px all rows keep the title and badges on one line, with the same boxes as before; the seeded row's title is 178px there, two lines, as today. 1280px was not measured with the inline styles; it has more room than 768px.

**Badges left-aligned when wrapped.** Drop `justify-end` from the group. On its own line the group fills the row, and `justify-end` would right-align badges under a left-aligned title. When the group shares the line, it is at its content width, so `justify-end` had no effect there. DESIGN.md asks for left alignment.

**E2E check in the existing demo test.** The demo visitor's login is throttled to 10 per minute per identity (`login_identity` in `backend/config/settings.py`). The suite already signs the demo visitor in 10 times across `demo`, `motion`, and `themes`. A new test with its own sign-in could be throttled. The assertions go at the end of `the demo visitor sees labelled, simulated data` instead.

**No unit test.** jsdom has no layout, so a Vitest test could only assert class names. The e2e test measures real boxes.

## Risks / Trade-offs

- [At phone width, rows differ: a row with one badge keeps it beside the title, a row with several puts them below] → Accepted for now. Revisit under #99 (cross-screen layout) if it reads as uneven.
- [The 12rem basis is a tuned number] → It lives in one class on one element and is the only value to change.
