# Frontend design

## Direction

The UI follows Quiet + craft: a compact workspace with one brand accent and
keyboard-first navigation. Surfaces stay neutral so status tones carry the
meaning. Depth separates resting content from what the member is working on.
Motion is short (100 to 220ms), only confirms a change, and is off under
`prefers-reduced-motion`.

## Tokens

All colours, typefaces, spacing, and radii live in
[`src/styles/theme.css`](src/styles/theme.css). Geist is the UI face. Geist
Mono is reserved for IDs, counts, shortcut hints, and small system indicators.
The base type size is 13px on desktop and 15px on phone.
The shadcn `--primary` token owns the brand accent. `--accent` is a muted
interaction surface.

## Themes

Light, dark, and system. `data-theme` on `<html>` always holds a concrete
theme; `src/lib/theme.ts` resolves system and saves the choice in this
browser, and an inline script in `index.html` applies it before first paint.
Members pick a theme under Settings, Appearance.

`:root` holds the light values. Each other theme is one
`:root[data-theme='…']` block that redefines every colour, tone, and
elevation token; a unit test fails if one is missing. Tailwind's `dark:`
variant follows `data-theme`, not the media query. Dark surfaces get lighter
as they rise, and dark shadows are stronger because they read less.

To add a theme, add its token block and its name to `THEMES` in
`src/lib/theme.ts`, then give it a picker option in `theme-settings.tsx`.

## Status tones

Every status uses `StatusBadge` with one of six tones: a tinted pill, a dot,
and a text label that is always shown. Features map their states to tones
next to their labels and never pick badge colours themselves.

| Tone     | Meaning                         | Examples                                   |
| -------- | ------------------------------- | ------------------------------------------ |
| neutral  | finished, inert, or not started | Dismissed, Not planned, Draft, No response |
| info     | new and waiting for triage      | New report, Open problem                   |
| progress | someone is working on it        | In progress, Queued, Contacted             |
| success  | resolved or delivered           | Linked, Fix available, Sent, Confirmed     |
| warning  | needs a person's attention      | Needs review, Uncertain, Still affected    |
| danger   | broken and needs action         | Failed                                     |

Use the shadcn `Badge` only for labels that are not a status, such as "Demo".

## Elevation

Three levels, as `shadow-elevation-1` to `-3`. Each draws its own 1px edge, so
a surface with elevation needs no border.

1. Resting: lists and cards.
2. Raised: the detail panel beside a list, and the sign-in card.
3. Floating: toasts and menus.

Boxes nested inside an elevated surface use a plain border.

## Wordmark

The wordmark is the SVG used as a mask over `--primary`, so it follows the
theme. In the sidebar it links to the inbox.

## Components

- StatusBadge: the only status pill
- shadcn primitives: Button, Badge, Card, Alert, Avatar, Separator, Skeleton, Input, Textarea, and NativeSelect
- form fields: Field, TextareaField, and SelectField share one label, hint, and inline error layout
- shared async states: LoadingState, EmptyState, ErrorState, RetryButton, and QueryState
- ActionError explains a failed save or triage action; the form that owns the input keeps it
- AppShell: desktop sidebar, mobile bottom navigation, and a compact status header

## Async state pattern

TanStack Query screens pass their query state to `QueryState`, or compose
LoadingState, EmptyState, and ErrorState directly when the empty state needs
screen-specific wording (the inbox separates "no reports yet" from "no
matches"). It renders one
of loading, empty, error, or ready. Errors explain the next action and retry
uses the same button everywhere. Preserve user input in the feature screen
that owns the draft when a recoverable request fails.

## Layout rules

- Desktop uses a sidebar, a flexible content area, and compact 44px navigation rows.
- Mobile keeps all navigation targets at a 44px minimum touch target and moves navigation to a bottom tab bar. Action controls use `touchTarget` for the same minimum.
- Controls use the smaller control radius. Cards use the larger card radius. Status badges are pills.
- Use left alignment, short text measure, visible focus, and no decorative colour outside the token system.

## Do and do not

- Do use semantic token classes and shared state components.
- Do keep primary actions short and name the result of the action.
- Do not add a second palette, inline colour, or per-screen loading pattern.
- Do not build product workflow UI in the shell or gallery.

## Follow-ups and settings

- A follow-up has two statuses. Show each with a muted term before its badge,
  "Delivery" and "Outcome", through `FollowUpStatuses`. The badge text stays
  the plain state, and a follow-up with no message reads "Not prepared".
- Detail facts use a `dl` with a fixed term column, not "Label: value" lines.
- Each integration is a `Card` with its name and `ConnectionStatusBadge` in
  the header. Job counts are four labelled numbers in Geist Mono, in the
  foreground colour, because counts are not statuses.
