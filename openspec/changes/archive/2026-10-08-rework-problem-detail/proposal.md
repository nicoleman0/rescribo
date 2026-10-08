# Proposal

## Why

Issue [#108](https://github.com/nicoleman0/rescribo/issues/108): problem detail repeats a full assignee form, helper text, and source block for every linked report (about 1,000px for six reports). Activity shows raw values such as "changed the needs_review" and one line per linked report. A problem marked "Needs review" gives no next step. Each linked report also renders its own `Provenance` landmark, which fails axe `landmark-unique` when a problem has more than one report. Direction and mockup: [#100](https://github.com/nicoleman0/rescribo/issues/100). Builds on the tone and elevation tokens from #110.

## What Changes

- Add a next-step banner under the problem header. Its tone and text follow the problem state and the needs-review flag.
- Put the fix, the GitHub issue, and the owner in a side column on wide screens. They stack below the header on phones.
- Show the owner as text. "Change" opens the owner form on demand.
- Show linked reports as compact rows: title link, status badge, customer, a one-line source, and the assignee as text. "Change" opens the existing assignee form for that row. "Confirm fix applies" stays on rows that need it.
- The full source (captured message, permalink, permalink retry) stays on the report page, one click from the row. Problem detail no longer renders a `Provenance` region per report.
- Group activity: consecutive links of reports by one member become one entry ("linked 6 reports") that expands to list them. Replace raw field names with labels, and describe GitHub issue events.
- Restore the full axe check on problem detail in the dark-theme e2e.
- Keep every action the page has today: edit title and summary, owner, link, create, refresh and replace a GitHub issue, confirm fix, confirm fix applies, and report reassignment. Move and ungroup stay in the inbox triage panel, where they are today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-interface`: adds requirements for the problem detail next step, compact linked reports, and grouped, labelled activity.

## Impact

Frontend only: `src/features/problems/`, `frontend/e2e/report-triage.spec.ts`, `frontend/e2e/themes.spec.ts`, and an appended section in `frontend/DESIGN.md`. No API, database, or worker changes. No shared component changes; inbox components are reused unchanged. The banner has no action that clears "Needs review" on a problem whose fix is available, because the backend has none. That action comes with [#113](https://github.com/nicoleman0/rescribo/issues/113).
