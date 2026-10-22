# Tasks

Delivers #220. Tooling only; `skip_specs: true`. Change only the four test files named below. Do not change app code, `src/test/`, or other test files. Do not add timeouts or retries.

Load run ("3x10"), from `frontend`: start 10 `yes > /dev/null`, run 3 `npx vitest run --reporter=verbose --reporter=json --outputFile.json=<dir>/<tag>-<n>.json` in parallel, wait for all three, stop the `yes` processes. One round is 3 runs; 4 rounds are 12. Keep outputs in a scratch directory, not the repo. Record `uptime` after each round.

## 1. Before

- [x] 1.1 Run 3x10 for 4 rounds on the unchanged tests. Record the failures per test (planner saw inbox "lists reports and sends search and filter changes to the API" fail 6 of 12, settings "members see connections but no owner controls" 1 of 12) and the max duration of each test in the four files. Verify: counts recorded for the PR.

## 2. Inbox in `frontend/src/features/inbox/inbox-page.test.tsx`

- [x] 2.1 In "lists reports and sends search and filter changes to the API", replace `const list = await screen.findByRole('list', { name: 'Reports' })` with `await screen.findByText('CSV export fails')` and `const list = screen.getByRole('list', { name: 'Reports' })`, under a one-line comment that the named role query is slow under load. Replace `await screen.findByRole('option', { name: 'Ada Lovelace' })` with `await screen.findByText('Ada Lovelace', { selector: 'option' })`. Then find the filter controls with `getByLabelText` (Search reports, Customer, Assignee, Source) and `getByText` (Search, Clear filters), and reuse the Linked chip found once by role. Verify: the file passes and the test passes 12 of 12 at 3x10 (5.1).

## 3. Recipient form in `frontend/src/features/follow-ups/follow-up-recipient-form.test.tsx`

- [x] 3.1 In each test, open the picker with `await screen.findByLabelText('Recipient: Ada Lovelace')` instead of `findByRole('combobox', ...)`, then assert once that it has role `combobox` (`getByRole('combobox', { name: 'Recipient: Ada Lovelace' })` or `toHaveAttribute('role', 'combobox')`). Verify: the file passes.
- [x] 3.2 Wait for each option by its text (`findByText`, scoped with `within` if the name also appears outside the list), then use `getByRole('option', { name })` once where the test clicks it or asserts its state. Verify: the file passes. If an option's text does not match its accessible name, stop and report it.

## 4. Command palette in `frontend/src/components/command-palette/command-palette.test.tsx`

- [x] 4.1 Change the `dialog()` helper to wait on `screen.findByPlaceholderText('Search screens, reports, and problems')` and return `screen.getByRole('dialog', { name: 'Command palette' })`. Verify: the file passes.
- [x] 4.2 Replace each `findByRole('option', { name })` and `findAllByRole('option', { name })` with a text wait scoped to the dialog, then one `getByRole`/`getAllByRole` for the asserted option. Keep the `waitFor` checks on `searches`, focus, and `queryByRole('dialog')` as they are. Verify: the file passes.

## 4b. Settings in `frontend/src/features/settings/settings-page.test.tsx`

- [x] 4b.1 In "members see connections but no owner controls", wait for the GitHub heading with a text query scoped to heading elements, then assert it once with `getByRole('heading', { name: 'GitHub' })`, under a one-line comment that the named role query is slow under load. Leave the negative checks as they are. Verify: the file passes.

## 5. After

- [x] 5.1 Run 3x10 for 4 rounds in the same session as 1.1. Verify: no failure in the three changed files in 12 runs. Record failures and max durations beside 1.1 for the PR. List any failure outside these files without fixing it.
- [x] 5.2 Show the new waits still catch a missing state: in a temporary edit, stub an empty report page in 2.1's test an empty member list in 3.1's first test, and a failing connections request in 4b.1's test, and confirm each fails on its text wait. Revert. Verify: noted for the PR.

## 6. Repository checks

- [x] 6.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 6.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.switchyard/brief.md`; do not start or stop services). `schema-check` reports no API change. Record the test counts for the PR.
- [x] 6.3 `RESCRIBO_E2E_API_PORT=8220 RESCRIBO_E2E_FRONTEND_PORT=5220 task e2e` passes. Do not run it during a load run. Record the counts for the PR.
- [x] 6.4 No `yes`, vitest, or dev server process from this worktree is left running, and no probe test files remain.

## Workflow follow-up

- Archive this change in the PR that completes #220 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": the bar is 3x10, not the issue's 2x6; waits use text, label, or placeholder then one role check; markdown and outcome are unchanged.
- PR Screenshots: "Not applicable: no visible change".
