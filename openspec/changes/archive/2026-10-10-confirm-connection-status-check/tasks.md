# Tasks

Delivers #144. Paths are from the repository root. Decisions D1 to D5 are in `design.md`. Frontend only: do not touch the backend, `frontend/openapi.yaml`, or `frontend/src/api/schema.d.ts`.

Do not change the `min-h-11` classes in `connection-settings.tsx` (#156), and do not change anything for #146 or #148.

Write the tests first (group 1) and see them fail, then build group 2.

## 1. Component tests in `frontend/src/features/settings/settings-page.test.tsx`

Add at the end of the file. Reuse `base`, `unlinked`, `render`, `slackConnection`, and the existing `afterEach`. Do not change existing tests. Scope queries with `within(screen.getByRole('region', { name: 'GitHub' }))` or `'Slack'`. A pass is `new Response(null, { status: 204 })`.

- [x] 1.1 Check passes: as owner with an active GitHub connection (`{ ...slackConnection, provider: 'github', repository: 'acme/app' }`), stub `POST ${base}connections/github/refresh/` with 204. Press "Check GitHub status". Assert the card's `role="status"` element contains "GitHub connection is working" and a `<time>` element, and that the request body is `{ version: 1 }`.
- [x] 1.2 Repeated check is distinct: with `vi.useFakeTimers({ toFake: ['Date'] })` and `vi.setSystemTime`, press the button at one time, read the `<time>` `dateTime`, move the clock 20 seconds, press again, and assert the `dateTime` changed. Restore real timers in a `finally`.
- [x] 1.3 Failure, then recovery: as owner with the Slack connection, the first `POST ${base}connections/slack/refresh/` answers `json({ detail: 'Grant the required Slack scopes and reconnect.', reason: 'missing_scopes', field_errors: {} }, 400)`. Assert a `role="alert"` in the Slack card contains "Slack check failed" and the detail, that "connection is working" is absent, and that "Connection update failed" is absent. The second answer is 204: assert the alert is gone and the status reads "Slack connection is working".
- [x] 1.4 Channel actions stay separate: with one allowed channel, a 204 on `POST ${base}channels/` after "Remove channel" shows no "connection is working". A 400 on it still shows "Connection update failed" and no "check failed".
- [x] 1.5 Passed result needs an active connection: the refresh answers 204 but the next `GET ${base}connections/` returns the connection with `status: 'error'`. Assert "connection is working" is absent.

## 2. `frontend/src/features/settings/connection-settings.tsx`

- [x] 2.1 Add `const check = useSettingsAction(workspaceId)` beside `action` (D1). The check button calls `check.mutate` with the same path and body as today. Disable the check button, both channel buttons, and the channel submit while `check.isPending || action.isPending`.
- [x] 2.2 Add a local `CheckResult` component that takes `name`, `check`, and whether the connection is active, and renders per D2 and D4: the always-mounted `<p role="status">` with the pending or passed text, and the `<p role="alert">` failure. Format the time from `check.submittedAt` with a module-level `Intl.DateTimeFormat(undefined, { timeStyle: 'medium' })` inside `<time dateTime>` (D3).
- [x] 2.3 Wrap the check button and `CheckResult` in `flex flex-wrap items-center gap-x-3 gap-y-2` (D4). Leave the button's own classes as they are.
- [x] 2.4 Leave the "Connection update failed" block on `action.error` only (D5). Leave the "Connection needs attention" block and the badge unchanged.
- [x] 2.5 Run `npm test -- settings-page` from `frontend` and see group 1 pass.

## 3. E2E and design notes

- [x] 3.1 One test in `frontend/e2e/settings.spec.ts`, mocked: sign in as `seed.users[1]` as "the Slack connect form passes API validation" does, stub `**/connections/slack/refresh/` with `route.fulfill({ status: 204 })`, press "Check Slack status" in the Slack region, and assert the status reads "Slack connection is working". Set a 390px viewport and assert the page has no horizontal overflow, then assert `axeViolations(page)` is empty. Comment in one line why the request is stubbed: a real check with the seeded fake credential would put the connection in `error`.
- [x] 3.2 If the coordinator approved it (Q5), add one bullet to `frontend/DESIGN.md` under "Follow-ups and settings": the result of a connection check shows beside its button as one status line, with the time to the second; a failure replaces it in the same place. Add the line only; do not reword existing text.
- [x] 3.3 After screenshots. Reseed with `seed_demo` and `seed_test_accounts --json`, start the dev servers on 8144 and 5144, then run `SHOTS_BASE=http://127.0.0.1:5144 node .claude/skills/work-issues/scripts/shots.mjs .claude/shots/after`, `SHOTS_BASE=http://127.0.0.1:5144 node .claude/shots/owner-shots.mjs .claude/shots/after`, and the same owner script again with `SHOTS_CHECK=pass` and with `SHOTS_CHECK=fail`. The owner script stubs the request; say so in the PR. Build `.claude/shots/compare.html` with `.claude/skills/work-issues/scripts/compare.py` from the `settings-owner-*` shots. Stop the dev servers.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8144 RESCRIBO_E2E_FRONTEND_PORT=5144 task e2e` passes.

## Workflow follow-up

- Archive the change in the PR that completes it.
