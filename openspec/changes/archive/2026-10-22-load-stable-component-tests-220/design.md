# Design

## Context

Load runs from `frontend` on 2026-10-22, 10 cores. "2x6" means 2 full `vitest run` in parallel plus 6 `yes > /dev/null`; each round counts as one run per suite.

| Load | Runs | Failures |
| --- | --- | --- |
| 2x6 (the issue's load) | 22 | none |
| 3x10 | 12 | inbox "lists reports ..." 6, settings "members see connections ..." 1 |
| 4x14 (load average about 109) | 12 | inbox "lists reports ..." 12, follow-ups pagination (#206's fix) 12, palette "opens from the trigger ..." 11, recipient "lets an owner change ..." 8, inbox "status chips ..." 9, palette others 11, settings 6, follow-ups list 3, problems list 2, markdown 1 |

The recipient form test the issue names (the "Ada Lovelace" option) was rewritten by #227; the picker now has a combobox named "Recipient: Ada Lovelace". Follow-up outcome never failed at any load.

Where the inbox test spends its time, from a timing probe (mean per step, 2x6):

- `findByRole('list', { name: 'Reports' })`: 685 ms, max 1007 ms against a 1000 ms budget.
- Each later step (a `getByRole` plus the render the action causes): 80 to 310 ms.
- Total 3.1 s at 2x6 and 4.5 s at 3x10, against the 5000 ms test timeout.

Idle, each query on the 102-element inbox page costs 0.3 to 3 ms, so the waits cost most where they poll through many renders. The first role query in a file costs about 80 ms idle (then about 1 ms); that lands on each file's first test and is not a query choice.

A probe copy of the inbox test with two cheap waits (`findByText('CSV export fails')` then `getByRole('list', ...)` once, and `findByText('Ada Lovelace', { selector: 'option' })`), run beside the original at 3x10: original 7 of 8 failed (4.9 to 6.3 s), copy 0 of 8 (2.4 to 4.7 s).

The inbox "status chips" `aria-pressed` failure appears only in runs where "lists reports ..." timed out first. A timed-out test keeps running and its `screen` queries and clicks land in the next test's DOM. It is a knock-on failure, not a component bug.

Maintainer decisions on the plan: the bar is 3x10 for 12 runs, before and after in one session. The settings test joins this change because it failed at 3x10. Follow-ups list, problems list, markdown, and outcome tests are unchanged; the PR records their numbers.

## Goals / Non-Goals

**Goals:**
- At 3x10 for 12 runs, no test in the changed files fails.
- Each changed wait polls a cheap query (text, label, placeholder, or a stub's recorded calls), and the role or accessible name is still asserted once after it.

**Non-Goals:**
- No raised `findBy`, `asyncUtilTimeout`, or test timeout, and no retries.
- No change to app code, `src/test/setup.ts`, or `src/test/render.tsx`.
- No pass at 4x14. At that load #206's fixed test fails 12 of 12, so it is past what the budgets survive.
- No rewrite of the other named-role waits in these areas (`report-actions.test.tsx` has 37, `follow-up-outcome.test.tsx` 10) while they do not fail.
- e2e tests (#221) and focus classes in component files (#225).

## Decisions

### Wait cheap, then check the role once

Same pattern as #206 (`follow-ups-page.test.tsx`): the wait polls `findByText`, `findByLabelText`, or `findByPlaceholderText`; one `getByRole` with the name follows, so the accessible role and name stay asserted. Where the text is not unique, scope it with `within` on an element already found once.

Alternatives: `{ hidden: true }` on the role query skips the accessibility-tree check and is about 3 times faster, but it no longer proves the element is exposed. Splitting the long inbox test into smaller tests gives each part its own 5 s budget, but changes the test's shape and the issue asks for cheaper waits.

### Per file

- Inbox "lists reports ...": the two waits from the probe. The other steps stay.
- Recipient form: open the picker through `findByLabelText('Recipient: Ada Lovelace')` (the trigger's `aria-label`), wait for each option by its text, then `getByRole('option', ...)` once where the test asserts its state.
- Inbox "lists reports ..." needed more than the two waits. At 3x10 with only those, it still timed out 6 of 12 (5.2 to 5.9 s): the other named role queries (two searchboxes, Search, two comboboxes, Clear filters) cost about 0.3 to 0.8 s each under load. The test now finds those controls with `getByLabelText` or `getByText`, takes the status group and the Linked chip by role once and reuses the chip, and keeps the role checks on the list, row, group and chip.
- Settings "members see connections ...": `findByText('GitHub', { selector: 'h2' })` (the heading element, so the text stays unique), then one `getByRole('heading', { name: 'GitHub' })`. The negative `queryBy` checks stay.
- Recipient option "Ada Lovelace (no Slack link)": the suffix is its own span, so the wait is `findByText('(no Slack link)')`, then the role check by the full name.
- Command palette: the `dialog()` helper waits on `findByPlaceholderText('Search screens, reports, and problems')`, then returns `getByRole('dialog', { name: 'Command palette' })`. Option waits by name become text waits scoped to the dialog, then one role check.

### Bar: 3x10, 12 runs

The issue's 2x6 does not fail on this machine today, so it cannot show a before and after. 3x10 fails the inbox test 6 of 12 and is below the 4x14 level where unrelated tests fail.

## Risks / Trade-offs

- [Load numbers depend on what else runs on the machine] → record the load average with each batch, and run before and after in the same session.
- [The inbox filter controls are no longer found by role in that one test] → `getByLabelText` still proves each accessible name. Other inbox tests still find the Customer searchbox and the Assignee combobox by role. The Search reports searchbox, Source combobox, and the Search and Clear filters buttons lose their role query. Flagged for review.
- [Text waits pass on text outside the element the test means] → each text wait is followed by the role check on the same element, which fails if the text matched elsewhere.
- [The palette and recipient tests still spend most of their time in renders and user events] → at 3x10 their max was 4.7 s and 4.4 s. The change keeps them within budget at the bar, not at 4x14.
