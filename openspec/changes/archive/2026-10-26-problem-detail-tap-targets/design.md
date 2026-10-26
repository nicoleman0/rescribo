# Design

## Context

Measured at 390 px on the seeded demo before the change:

| Target | File | Height | Display |
| --- | --- | --- | --- |
| Linked report title | `problem-detail-page.tsx` `LinkedReports` | 21.75 (43.50 when it wraps) | flex item |
| "linked N reports" summary | `problem-activity.tsx` `ActivityRow` | 18.75 | `list-item` |
| Report links inside the opened summary | `problem-activity.tsx` `reportLink` | 17 | inline |
| GitHub issue link | `github-issue-status.tsx` | 17, or 35.75 on two lines | inline |
| Release tag link | `problem-detail-page.tsx` `FixCard` | 18.75 | grid item |
| Fix evidence link | `problem-detail-page.tsx` `FixCard` | not seeded; same classes as the release link | grid item |
| "Open issue #N" | `github-issue-create.tsx` | not seeded; `text-sm` | grid item |
| "Open workspace settings" | `github-issue-create.tsx` `ConnectionGuidance` | not seeded; `text-sm` | grid item |

Already 44 px: Back to problems, the next-step actions, and every other `Button`. The Status card and the no-reports offer from #181 have no links; the offer is a `Button`.

`touchTarget` (`max-md:min-h-[44px]`) has no effect on an inline element, and on a block it leaves the text at the top of the box.

## Goals / Non-Goals

**Goals:**
- Each standalone link reaches 44 px at phone width with its text centred.

**Non-Goals:**
- Other pages. A sweep of the demo inbox, report detail, follow-ups list and detail, and settings at 390 px found no standalone link under 44 px.
- Changing link colour, underline, or spacing.

## Decisions

- **Links: `inline-flex items-center` plus `touchTarget`.** `inline-flex` lets `min-height` apply to links that were inline and centres the text. In grid and flex parents the item is blockified to `flex`, which still works. Checked in the browser: every link measured 44.00 with no horizontal overflow, and long issue titles still wrap. Alternative: `block` plus `content-center`. It would change `w-fit` links to full width in some parents, so the tap area would grow past the text.
- **One feature-local class for links.** Add `standaloneLink = cn('inline-flex items-center', touchTarget)` to `problem-card.ts`, next to the other shared class strings of the feature. Each site adds its own colour classes. The 44 px value stays in `touchTarget` only. Alternative: export it from `components/layout/touch-target.ts`. That file is shared and outside this issue's paths; move it there when a second feature needs it.
- **Summary: `touchTarget` plus `content-center`, keep `list-item`.** `display: flex` on `<summary>` removes the disclosure triangle. `align-content: center` centres block content and keeps the marker. Checked in the browser: 44.00 with the triangle in place.
- **Inline links stay as they are.** The activity sentence links ("moved X here from Y", "assigned X to Y") and "Open settings" in the release picker's error sentence are inside running text, which WCAG 2.5.8 exempts.
- **Spec delta, not `skip_specs`.** `web-interface` states 44 px targets for the follow-up page, the command palette, pickers, and settings, but no requirement covers problem detail links. This adds one.
- **One e2e test in `demo.spec.ts`.** The demo problem "Password reset emails arrive after the link expires" has six linked reports, a folded "linked 6 reports" entry, a release link, and a GitHub issue link. `demo.spec.ts` already opens it at 390 px. The test uses `expectTouchTarget` for each target, opens the summary and measures the revealed links, and checks no horizontal overflow. Fix evidence, "Open issue #N", and "Open workspace settings" are not in the seed; they share the class with measured links, so they are not measured separately.

## Risks / Trade-offs

- [Phone rows get taller: each linked report row grows by about 22 px, and the opened activity group by about 27 px per link] → Accepted. That is the cost of the target size. Desktop is unchanged.
- [A future link on problem detail misses the class] → The DESIGN.md line names the rule; the e2e test catches the seeded ones.
