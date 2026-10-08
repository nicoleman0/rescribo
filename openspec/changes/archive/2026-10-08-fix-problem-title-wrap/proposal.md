# Proposal

Delivers GitHub issue #122 (milestone E. UI polish).

## Why

On phones the problems list squeezes long titles into a column one letter wide. The badge group beside the title has `shrink-0`, so it takes the row width first. The seeded "Password reset emails arrive after the link expires" row (Needs review, Fix available, GitHub chip) shows it at 390px. Its GitHub chip also runs past the card edge and is clipped.

## What Changes

- The title and badge group in each problems list row wrap as two flex items. The title keeps at least 12rem. When the badges do not fit beside it, they move to the next line, left-aligned, and wrap among themselves.
- Desktop rows look the same as before: the title is on the left and the badges are on the right of the same line.
- The demo e2e test checks the seeded row at 390px and 1280px.

No behaviour, API, or spec change. The change sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. Layout only.

## Impact

- `frontend/src/features/problems/problems-page.tsx` (`ProblemList` row markup only).
- `frontend/e2e/demo.spec.ts` (new assertions in the existing demo test).
- `frontend/DESIGN.md` (a new "Problems list" section appended at the end).
