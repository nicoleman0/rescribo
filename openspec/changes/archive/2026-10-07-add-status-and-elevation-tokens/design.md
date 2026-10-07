# Design

## Context

Badge colours live in three feature modules: `inbox/triage-badge.tsx`, `problems/problem-state.tsx`, and `follow-ups/follow-ups-format.ts`. They mix `bg-primary`, `bg-selected`, `bg-muted`, `bg-linked`, `bg-needs-review`, and `bg-destructive/10`, so "new" is a filled primary pill while "queued" is a grey one. `Card` draws its edge with `ring-1 ring-foreground/10` and nothing else has a shadow. The wordmark is an `<img>` of an SVG with a hard-coded `#4a2a6e` fill.

The mockup in #100 is a throwaway prototype. Its tokens and tone mapping are ported; its markup is not.

## Goals / Non-Goals

**Goals:**
- One authoritative home for each tone's colours (`theme.css`) and one for each state's tone (the feature's format module).
- A wordmark whose colour comes from `--primary`, so #101 only needs to add dark tokens.

**Non-Goals:**
- Dark tokens, theme picker (#101). Motion and badge colour transitions (#106).
- Labelling follow-up delivery and outcome badges distinctly, or reworking screen layouts (#107 to #109).
- Changing the shadcn `Badge` primitive, which stays for non-status labels such as "Demo".

## Decisions

### Tone tokens

Each tone has three tokens in `:root`: `--tone-<name>`, `--tone-<name>-foreground`, `--tone-<name>-dot`, exposed to Tailwind through `@theme inline` as `bg-tone-<name>` and friends. Values are the mockup's light palette. The `--linked*` and `--needs-review*` tokens are removed because their only users move to tones; keeping both would be two names for one colour.

### StatusBadge

`components/status/status-badge.tsx` takes `tone` and children and renders a pill with a 6px dot (`aria-hidden`) and the label. Tone classes are a `cva` variant map, so the full class strings are literal for Tailwind's scanner. It sets `data-tone` for tests and for #106's transitions.

Feature components keep the state-to-tone mapping, because that is domain knowledge, and render `StatusBadge`. `TriageBadge`, `ProblemStateBadge`, and `NeedsReviewBadge` stay as thin wrappers so call sites do not change. Follow-ups replace `deliveryBadgeClass` and `contactBadgeClass` with `deliveryTone` and `contactTone`.

Alternative considered: a `tone` variant on the shadcn `Badge`. Rejected because the dot and label structure would leak into a generic primitive, and shadcn updates would conflict.

### Tone mapping

| State | Tone |
|---|---|
| Report: new, linked, dismissed | info, success, neutral |
| Problem: open, in progress, fix available, not planned | info, progress, success, neutral |
| Problem needs review | warning |
| Delivery: draft, queued, sent, uncertain, failed, cancelled | neutral, progress, success, warning, danger, neutral |
| Contact: pending, contacted, confirmed, still affected, no response | neutral, progress, success, warning, neutral |
| Follow-up not prepared | neutral |

Report and problem rows follow the mockup. Follow-up rows are not in the mockup and follow the same rule: waiting on someone is progress, needs attention is warning, broken is danger, finished or inert is neutral or success.

### Elevation

Three tokens, `--elevation-1` (resting: cards, lists), `--elevation-2` (raised: detail panels, the auth card), `--elevation-3` (floating: toasts, menus). Each includes a 1px `--border` ring, so a surface using one needs no separate border. Exposed as `shadow-elevation-1` to `-3`. `Card` swaps its ring for level 1. Most screens draw their own bordered surfaces instead of `Card`, so the three top-level lists (inbox, problems, follow-ups) move to level 1 and the report and follow-up detail panels to level 2. Nested bordered boxes inside those surfaces keep their plain border. The empty state, which opts out of depth, gets an explicit dashed border instead of relying on the ring.

### Wordmark

The wordmark renders as a `span` with `role="img"`, the SVG as a CSS mask, and `bg-primary`. The SVG file stays the single source of the letterforms. Under forced colours it uses `CanvasText` so it stays visible. In the sidebar it sits inside a router `Link` to `/inbox` with the accessible name "rescribo, go to inbox".

Alternative considered: inline the SVG with `fill="currentColor"` via `?raw`. Rejected because it needs `dangerouslySetInnerHTML` for a 16KB path.

## Risks / Trade-offs

- [The "new" badge loses its filled primary fill and may draw less attention] → The info tone keeps the brand hue and the dot; #107 moves status to the left edge of rows.
- [Shadow ring differs slightly from the old `ring-foreground/10`] → Compared in before/after screenshots.
