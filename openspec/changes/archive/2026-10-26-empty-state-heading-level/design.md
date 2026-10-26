# Design

## Context

`EmptyState` in `frontend/src/components/states/async-states.tsx` hard-codes its title as `h1`. `QueryState` renders it for the empty status. There are 19 direct call sites plus `QueryState`:

| Call site | Sits under a page `h1`? | Level |
| --- | --- | --- |
| `App.tsx` not-found route | No, only content of `<main>` | 1 |
| `require-auth.tsx` "Workspace access removed" | No, rendered instead of the shell | 1 |
| `inbox-page.tsx` (4: bad page, bad filters, no matches, no reports) | Yes, "Inbox" | 2 |
| `report-detail.tsx` (2: not found, access removed) | Yes, always a panel inside the inbox page | 2 |
| `problems-page.tsx` (4) | Yes, "Problems" | 2 |
| `problem-detail-page.tsx` (2: not found, access removed) | No, the page `h1` only renders with data | 1 |
| `follow-ups-page.tsx` (2) | Yes, "Follow-ups" | 2 |
| `follow-up-detail.tsx` (2: not found, access removed) | Panel: yes. Full page: no | `page` → 1, `panel` → 2 |
| `dev/ui-gallery.tsx` | Yes, gallery `h1` | 2 |
| `QueryState` empty status (used only in the gallery and tests) | Yes | 2 |

The problem and follow-up detail views already hide their body, and its `h1`, when a refetch returns 403 or 404, so a full-page state title never sits beside a record title.

`report-detail.tsx` only renders as a panel; there is no standalone report page.

## Goals / Non-Goals

**Goals:**
- One level-1 heading on every page listed above.
- A new list-page empty state gets the right level without the author choosing.

**Non-Goals:**
- A general heading-level context or offset for the app.
- Visual change. The title keeps its current classes.
- Other `h1` sources (`settings-sections.tsx`, auth layout), which already render one each.

## Decisions

- **`level?: 1 | 2` prop, default 2.** Nested use is the common case (14 of 20 sites; 6 are whole-page or depend on layout) and the one people copy when they add a list page. Whole-page use is rare and deliberate: a route fallback or an access gate. A forgotten `level={1}` leaves a page with no `h1`, which the page tests below catch.
  - Alternative: default 1 (today's behaviour) and opt in to 2. Rejected: the mistake this issue reports is the default one.
  - Alternative: required `level` prop. Every author decides and TypeScript enforces it, at the cost of a prop on all 20 sites. Kept as an option for review.
  - Alternative: React context that page shells set. Rejected: more machinery than two levels need.
- **The type is `1 | 2`, not 1 to 6.** No current site needs a third level. The gallery puts the state under a section `h2`, so a sibling `h2` there is acceptable for a dev page.
- **Follow-up detail derives the level from `layout`**, the same rule as its existing `Title` (`layout === 'panel' ? 'h2' : 'h1'`). Compute it once in `FollowUpDetailContent` and pass it to both states.
- **Tests at the page level, not e2e.** The page tests (`inbox-page`, `follow-ups-page`, `problems-page`, `follow-up-detail-page`, `require-auth`) render the full page with a mocked API, so they can count level-1 headings. No e2e test is added; `z-product-states.spec.ts` runs on seeded data with rows, and an empty-filter e2e case would repeat what the page tests prove.
- **Spec requirement, not `skip_specs`.** Heading levels are what screen reader users navigate by, so this is observable behaviour. No spec covers app pages yet (the auth rule at `web-interface/spec.md:524` covers only signed-out pages), so the change adds one requirement.

- **"Workspace access removed" gets a `<main>` wrapper.** It renders outside the shell, so it has no landmark today. The error branch beside it already wraps in `<main className="mx-auto max-w-xl p-6">`; this state does the same. A small separate fix, named as such in the PR.

## Risks / Trade-offs

- [A future whole-page empty state forgets `level={1}`] → The requirement and the page-level test pattern name the case; the DESIGN.md note says when to pass it.
- [Visual hierarchy unchanged while semantics change] → Intended. The title styling never matched an `h1`.
