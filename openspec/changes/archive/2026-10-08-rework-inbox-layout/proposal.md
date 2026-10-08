# Proposal

## Why

Issue [#107](https://github.com/nicoleman0/rescribo/issues/107): inbox rows wrap to three lines when a report is open, the status sits at the far right, and on a phone the filters fill the first screen so the list starts below the fold. Direction and mockup: [#100](https://github.com/nicoleman0/rescribo/issues/100) (Quiet + craft). Builds on the status tones and elevation from #110.

## What Changes

- Inbox rows become one line at desktop width: status badge first, then title, customer, assignee, and date. When the list is narrow (a report is open, or phone width) a row shows the status, the title, and a second line with customer and date.
- Status filtering moves from a select to chips (All, New, Linked, Dismissed), each with the number of reports that match the other active filters.
- The report panel stays raised beside the list and remains in view while the list scrolls. Triage actions move above the report details.
- At phone width, the report search and one Filters button stay visible. Customer search, status chips, assignee, and source open behind that button, which shows how many filters are active.
- Not in this change: the suggested problem with a direct "Link to problem" action in the report panel. It is left to `add-match-review-interface` (#21). "Link to problem" keeps working as it does today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds requirements for scannable inbox rows with the report panel beside the list, status chips with counts, and filters behind one button at phone width.

## Impact

Frontend only, inside `frontend/src/features/inbox/`, plus the inbox e2e selectors and `frontend/DESIGN.md`. Chip counts reuse the existing report list endpoint. No API, database, or worker changes. No new dependency.
