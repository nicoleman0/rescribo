# Design

## Context

`index.css` applies `focus-ring` (a 2px solid outline) to `button:focus-visible` and `a:focus-visible`. Tailwind 4's `transition`, `transition-all`, and `transition-colors` all include `outline-color`, with a 150 ms default duration. Ungated, the outline colour fades in on focus even under `prefers-reduced-motion: reduce`. `frontend/DESIGN.md` (Focus section) already says to gate these with `motion-safe:`, and #225 did so in `badge.tsx` and `input-group.tsx`.

Sweep of `frontend/src/components/ui/*.tsx` for transition utilities:

| File | Class | Element | Outcome |
| --- | --- | --- | --- |
| `breadcrumb.tsx:52` | `transition-colors` | `BreadcrumbLink`, an `a` with the focus ring | Gate |
| `sidebar.tsx:267` | `transition-all` | `SidebarRail`, a `button` | Gate |
| `sheet.tsx:65` | `transition` | `SheetContent`, a `div` | Leave (see Decisions) |
| `badge.tsx:7` | `motion-safe:transition-all` | Badge | Already gated |
| `input-group.tsx:17` | `motion-safe:transition-colors` | Input group | Already gated |
| `sidebar.tsx` 196, 208, 380, 400, 445, 530 | `transition-[width]`, `transition-[left,right,width]`, `transition-[margin,opacity]`, `transition-transform`, `transition-[width,height,padding]` | Various | Out of scope: no outline property |

## Goals / Non-Goals

**Goals:**
- No focus target in `components/ui/` animates its outline under reduced motion.

**Non-Goals:**
- Non-outline transitions in `sidebar.tsx`, and the sheet's slide animation.
- Feature components outside `components/ui/`.
- A lint or source-scan guard against future ungated transitions.

## Decisions

- **Gate with `motion-safe:`, as #225 did.** The hover colour change on the breadcrumb link stops fading under reduced motion too, which the spec requires. Alternative: narrow the property to `transition-[color]`. It would keep a colour fade under reduced motion, which the spec forbids.
- **Gate `SidebarRail` although the app does not render it.** No file outside `components/ui/` imports it, and its `tabIndex={-1}` keeps it out of keyboard focus. The issue names it, the fix is one prefix, and it stops the pattern from being copied when the rail is used.
- **Leave `SheetContent`.** It is a `div` that Radix gives `tabIndex={-1}`. The base focus ring targets only `button` and `a`, and Radix moves focus to the first focusable child on open, so the content does not draw a focus outline. Its open and close motion comes from `animate-in` and `animate-out` keyframes, not the transition. Whether the mobile sidebar sheet's slide runs under reduced motion is a separate question from this issue.
- **Breadcrumb test in `motion.spec.ts`.** In the existing "Reduced motion" block, open `/inbox/new`, which shows an "Inbox" breadcrumb link. Focus it from the keyboard and assert `transition-duration` is `0s` and `outline-style` is `solid`. Before the fix the duration is `0.15s`, so the test fails first. The `outline-style` check shows the ring still draws.
- **Rail unit test by class.** The rail is not in the app, so e2e cannot reach it, and jsdom does not evaluate media queries. A unit test renders `SidebarRail` inside `SidebarProvider` and asserts it has `motion-safe:transition-all` and not `transition-all`, matching the class check in `button.test.tsx`.
- **No DESIGN.md change.** The Focus section already states the rule.

## Risks / Trade-offs

- [The e2e assertion depends on Tailwind's 150 ms default] → It asserts `0s` after the fix, not the old value, so a default change does not break it.
