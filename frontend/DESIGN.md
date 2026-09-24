# Frontend design

## Direction

The UI follows direction A, Quiet: a light, compact workspace with one brand
accent and keyboard-first navigation. Surfaces stay neutral so triage states
carry the meaning.

## Tokens

All colours, typefaces, spacing, and radii live in
[`src/styles/theme.css`](src/styles/theme.css). Geist is the UI face. Geist
Mono is reserved for IDs, counts, shortcut hints, and small system indicators.
The base type size is 13px on desktop and 15px on phone.
The shadcn `--primary` token owns the brand accent. `--accent` is a muted
interaction surface.

## Components

- shadcn primitives: Button, Badge, Card, Alert, Avatar, Separator, Skeleton, Input, Textarea, and NativeSelect
- form fields: Field, TextareaField, and SelectField share one label, hint, and inline error layout
- shared async states: LoadingState, EmptyState, ErrorState, RetryButton, and QueryState
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
- Mobile keeps all navigation targets at a 44px minimum touch target and moves navigation to a bottom tab bar.
- Controls use the smaller control radius. Cards use the larger card radius. Status chips are pills.
- Use left alignment, short text measure, visible focus, and no decorative colour outside the token system.

## Do and do not

- Do use semantic token classes and shared state components.
- Do keep primary actions short and name the result of the action.
- Do not add a second palette, inline colour, or per-screen loading pattern.
- Do not build product workflow UI in the shell or gallery.
