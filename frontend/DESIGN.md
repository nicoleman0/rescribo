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
2. Raised: the report and follow-up detail panels and the sign-in card use
   `surface-raised` with `shadow-elevation-2`.
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
- Mobile keeps all navigation targets at a 44px minimum touch target and moves navigation to a bottom tab bar. `Button`, `Input`, and `NativeSelect` carry the 44px phone minimum themselves; other action controls (chips, tabs, option rows, checkbox labels) use `touchTarget`.
- Controls use the smaller control radius. Cards use the larger card radius. Status badges are pills.
- AppShell renders "Skip to main content" before the sidebar, so it is the first Tab stop.
- AppShell keeps Sign out in the header at every width. The sidebar has no sign-out block, and the UI gallery shows no Sign out.
- Use left alignment, short text measure, visible focus, and no decorative colour outside the token system.

## Page frame

- AppShell owns the shared content column width. Feature pages use the full column and constrain forms or prose locally.
- Pages set the document title with `PageTitle`, which appends the Rescribo name.

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
- The result of a connection check shows beside its button as one status
  line with the time to the second. A failure replaces it in the same place.

## Inbox

- Rows are one line: status badge first, then title, customer, assignee
  avatar, and a short date. The list is a container; when it is narrow (a
  report is open, or phone width) a row shows the badge, the title, and a
  customer and date line.
- Status filters are chips with counts. Each count is the list query for that
  chip with the other active filters.
- The report panel sits beside the list at elevation 2 and stays in view on
  desktop. Triage comes before the report details.
- On phones only the report search and a Filters button show; the button
  opens the other filters and shows how many are active.

## Problem detail

- A next-step banner sits under the header. `ProblemNextStep` picks its tone,
  heading, and links from the problem state and the needs-review flag. It
  and `StatusBadge` share `toneSurfaceClasses` for each tone's surface.
- Values a member changes now and then (owner, report assignee) show as text
  with a Change button. The button toggles the form and stays in place, so
  focus is not lost. A failed save never closes the form, so its input and
  error stay. The owner form closes after a save; `ReportAssigneeEditor`
  wraps the inbox assignee form, which has no save callback, so it closes
  only on Done.
- Side-column cards use `problemCard`: elevation level 1 and the card radius.
- "Mark reviewed" is the review banner's only write action. Its error stays
  visible when the banner changes step, and focus moves to the banner heading
  after success.

## Motion

Motion values live in `theme.css`: `--duration-fast` (100ms),
`--duration-base` (160ms), `--duration-slow` (220ms), `--ease-out-soft`,
and `--stagger-step` (22ms). All six motion utilities apply only under
`prefers-reduced-motion: no-preference`:

- `animate-page-enter`: fade and 4px rise on each feature page root.
- `animate-content-enter`: content fade, owned by `ReadyState` in the shared
  async states. Use it for ready content after `LoadingState`.
- `stagger-rows`: fade and 4px rise for mounted rows in the inbox, problems,
  and follow-ups lists. Delay is the zero-based row index times the stagger
  step, capped at index 10. Existing rows stay still on refetch.
- `animate-panel-enter`: fade and 12px slide on the unkeyed panel slot.
  Switching items fades the ready body and keeps the slot and list state.
- `transition-status`: badge and dot colour transitions.
- `press`: 0.97 button scale on press, except popup triggers. Colour, border,
  shadow, and scale transitions use the fast duration.

`surface-raised` uses `--raised` (white in light, lighter than cards in dark)
and scopes `--muted` to `--raised-muted` for fills and hover states inside it.
Outline and secondary buttons use `shadow-hairline`: a 3% black shadow in
light and a 50% black shadow in dark. Reduced motion keeps the resulting
colours and shadows and applies no animated transition.

## Problems list

- A row's title keeps at least 12rem. When the badges do not fit beside
  it, they move under the title, left-aligned, and wrap. No breakpoint is
  involved, so the rule holds beside the sidebar and on phones.

## Follow-up page

- `FollowUpDetailContent` owns the shared detail query, async states, and
  actions. `FollowUpDetailPanel` and `FollowUpDetailPage` choose its layout.
- The page puts its summary across the top. At `lg`, Message and Customer
  contact sit left; Recipient and History sit in a 20rem right column. Phones
  keep that order in one column.
- Panel sections stay bordered inside `surface-raised`. Page sections use
  `problemCard` as resting cards.
- The panel title is `h2` and its section headings are `h3`. The page title is
  `h1` and its section headings are `h2`.
