# Design

## Context

See proposal.md "Why" for the three causes. The evidence behind each:

- Triage: with `**/api/auth/csrf/` delayed 1500 ms after the click, the unchanged test fails on the last `toHaveCount(0)` with a count of 1; with a wait on the confirm response it passes. `reportAction` in `frontend/src/api/reports.ts` awaits `csrf()` before the `POST`. `ConfirmFixApplies` in `frontend/src/features/problems/problem-detail-page.tsx` renders "Recording…" while the mutation is pending.
- Follow-ups: timing probe in a temporary copy of the test. Idle: click to page-2 link in 49 ms, one `queryAllByRole('link')` in 17 ms. Full suite with 12 CPU spinners: up to 251 ms per role query. Three full suites in parallel with 10 spinners: up to 825 ms per role query, and the unchanged test failed 15 of 15 runs, 14 with the issue's error (`Unable to find role="link" and name /Page two report/`).
- Slack seed: a temporary backend test ran `seed_test_accounts`, added `C0E2EPUBLIC` to the `e2e-test` connection, ran the command again, and found the row still there. The picker filters out channels already in `connection.channels` (`allowed-channels.tsx`).

## Goals / Non-Goals

**Goals:**
- Each test waits on the state it depends on, and stays within its budget on a loaded machine.
- The e2e seed starts the `e2e-test` workspace with no allowed Slack channels.

**Non-Goals:**
- No app code change. No change to shared e2e helpers, `auth.setup.ts`, or `playwright.config.ts`.
- No raised `asyncUtilTimeout`, `findBy` timeout, or Playwright retry.
- The other component tests that failed under the heavy load (command palette, markdown, recipient form, inbox) are not in this issue.

## Decisions

### Triage: wait for the confirm response

Start `page.waitForResponse` for the `POST .../confirm-fix-applies/` before the click, and assert `response.ok()` before `page.reload()`. Keep `toHaveCount(0)` after it.

Alternatives: wait for the "Verify this existing fix applies to this report." text to disappear. That follows the refetch, so it also proves the save, but it ties the test to copy that may change. The response is the state the reload depends on.

### Follow-ups: wait on text, then check the role once

The test already waits on the right state (the page-2 row). What fails is the check: `findByRole` with a name runs an accessible-name pass over the whole page on every DOM mutation and every 50 ms, and the 25-row swap causes many mutations. Under load those checks fill the 1000 ms budget.

`findByText` waits for the same row with a cheap check. One `getByRole` after it keeps the link assertion.

Compared with 2 full suites in parallel and 6 CPU spinners, 16 runs each:

| Variant | Failures |
| --- | --- |
| Unchanged | 16 / 16 |
| Page 1 stub with 1 row, count 26 | 1 / 16 (at "Next page") |
| `findByText`, then `getByRole` | 0 / 16 |

With 3 suites and 10 spinners every variant fails, mostly at the first `findBy`, and unrelated tests fail too. That load is past what any `findBy` budget survives, so it is not the bar.

Alternatives: shrink the page-1 stub (above; it works less well and makes the fixture unlike the API); raise `asyncUtilTimeout` in `src/test/setup.ts` (a timeout, and a shared file).

### Keyboard navigation: drive Next with `userEvent`

The test name claims keyboard navigation, but it fires `keyDown` and `click` directly on Next, so it would pass even if Enter did nothing. `userEvent.keyboard`/`press` dispatches the real event chain, and the package is already a dependency (used in `follow-up-recipient-form.test.tsx`). The test focuses Next and presses Enter only, with no click; removing the press must fail the test on the page-two wait.

The approved plan added this while the issue was open, on top of the flake fix.

### Slack seed: delete the e2e workspace's allowed channels

Add `AllowedChannel.objects.filter(connection__workspace=workspace).delete()` with the other per-workspace deletes at the top of `handle`, where `workspace` is `e2e-test`. `e2e-settings` is already deleted and recreated, so its connection and channels go with it. `e2e-shell` has no Slack connection. The demo and all other workspaces are outside the filter.

The backend test builds a `demo`-slug workspace and an unrelated workspace with builders, each with its own Slack connection (distinct `external_id`, because of `one_active_slack_team`) and one allowed channel. Running `seed_demo` would cost time and test nothing extra, since the filter is by workspace.

## Risks / Trade-offs

- [The triage reproduction delays the CSRF request on purpose, so it widens a window CI hits by chance] → the planner ran it: unchanged, the test fails on the last `toHaveCount(0)` with 1 (the issue's symptom); with the response wait it passes. Delaying the `POST` itself does not reproduce it, because Playwright still delivers a routed request after the reload.
- [Other component tests use the same costly `findByRole` pattern and failed under load too: recipient form "Ada Lovelace" option, command palette, markdown, inbox] → out of scope; listed for a follow-up issue.
