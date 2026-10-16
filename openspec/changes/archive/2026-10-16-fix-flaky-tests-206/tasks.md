# Tasks

Delivers #206. Tooling only; `skip_specs: true`. Change only the files named below. Do not change app code, shared e2e helpers (`frontend/e2e/*.ts` other than the two specs named here), `auth.setup.ts`, `playwright.config.ts`, or `frontend/e2e/motion.spec.ts` (#192). Do not add timeouts or retries.

The three fixes are independent. In each group, show the failure first, then fix it.

Run e2e as `RESCRIBO_E2E_API_PORT=8206 RESCRIBO_E2E_FRONTEND_PORT=5206 npx playwright test ...` from `frontend`. Do not run load or vitest loops at the same time as e2e: the seed step times out under that load.

## 1. Triage reload in `frontend/e2e/report-triage.spec.ts`

- [x] 1.1 Reproduce. In the test "confirms fixes after moving a report and verifies applicability for a late report", add this just before `await confirm.click()`, run the test once, and record that it fails on the last `toHaveCount(0)` with a count of 1:

  ```ts
  await page.route('**/api/auth/csrf/', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.continue().catch(() => {})
  })
  ```

- [x] 1.2 Fix. Replace `await confirm.click()` and the `toHaveCount(0)` after it with:

  ```ts
  // The button reads "Recording…" while the CSRF and confirm requests run,
  // so its count drops before the confirmation is saved.
  const confirmed = page.waitForResponse(
    (response) =>
      response.url().includes('/confirm-fix-applies/') &&
      response.request().method() === 'POST',
  )
  await confirm.click()
  expect((await confirmed).ok()).toBe(true)
  await expect(confirm).toHaveCount(0)
  ```

  Rerun with the 1.1 route still in place. Verify: passes.
- [x] 1.3 Remove the 1.1 route. Run the test with `--repeat-each=20`. Verify: 20 passed. Record the numbers for the PR.

## 2. Follow-ups pagination in `frontend/src/features/follow-ups/follow-ups-page.test.tsx`

- [x] 2.1 Reproduce. From `frontend`, start 6 `yes > /dev/null` processes and run 2 full `npx vitest run --reporter=verbose` in parallel, 8 rounds (16 runs). Stop the `yes` processes. Record how often "paginates follow-ups, resets on bucket change, and supports keyboard navigation" fails (planner saw 16 of 16, all `Unable to find role="link" and name /Page two report/`).
- [x] 2.2 Fix. In that test, wait for each new row by its text, then get the link by role once:

  ```tsx
  // A role query over the 25-row page is slow under load; wait on the
  // cheap text query, then check the accessible link once.
  await screen.findByText('Page two report')
  const secondPageLink = screen.getByRole('link', { name: /Page two report/ })
  ```

  Do the same for `Failed delivery` and `bucketLink`. Leave the rest of the test as it is. Verify: the file passes.
- [x] 2.4 Keyboard navigation (from the approved plan): replace `fireEvent.keyDown` and `fireEvent.click` on Next with `userEvent` (`@testing-library/user-event`; see `follow-up-recipient-form.test.tsx`): focus Next and press Enter only, with no click. Show the test still tests the keyboard: with the Enter press removed, it fails on the page-two wait. Verify: the file passes. If pressing Enter does not move to page two, stop and report it (an app bug, not part of this issue).
- [x] 2.3 Repeat 2.1 with the fix, running after 2.4. Verify: 0 failures of this test in 16 runs. Record the numbers for the PR.

## 3. Slack channel seed

- [x] 3.1 Add `backend/tests/test_seed_test_accounts.py` with `pytestmark = pytest.mark.django_db` and one test. Arrange: a workspace with slug `demo` and `is_demo=True`, and a second unrelated workspace, built with `builders.make_workspace`. Give each a Slack `Connection` (distinct non-empty `external_id`, not `T0E2E`, status active) and one `AllowedChannel`. Act: `call_command("seed_test_accounts", stdout=StringIO())`, add an `AllowedChannel` for `C0E2EPUBLIC` to the `e2e-test` Slack connection, then run the command again. Assert: the `e2e-test` connection has no allowed channels; the demo and the unrelated workspace each still have theirs. Verify: the test fails on the first assertion before 3.2.
- [x] 3.2 In `backend/accounts/management/commands/seed_test_accounts.py`, import `AllowedChannel` and add `AllowedChannel.objects.filter(connection__workspace=workspace).delete()` with the other per-workspace deletes at the top of `handle`. Verify: 3.1 passes.
- [x] 3.3 In `frontend/e2e/settings.spec.ts`, run "an owner allows and removes a Slack channel from the picker" with `--repeat-each=20`. Verify: 20 passed. Done as 4 batches of `--repeat-each=5` with 62 s between them: the test signs in on every repeat, and the `login_identity` throttle (`10/min`) turns a single 20-repeat invocation into 429s at sign-in, unrelated to the seed. Every repeat past sign-in passed. Record the numbers for the PR.

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (ports in `.claude/brief.md`; do not start or stop services). `schema-check` reports no API change. Record the test counts for the PR.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8206 RESCRIBO_E2E_FRONTEND_PORT=5206 task e2e` passes. Record the counts for the PR.
- [x] 4.4 No dev server, `yes` process, or Celery worker from this worktree is left running. No `zz-*` probe files remain.

## Workflow follow-up

- Archive this change in the PR that completes #206 (`/opsx:archive`).
- PR milestone: G. Manual check findings.
- PR "Decisions to review": wait on the confirm response rather than on UI copy; the follow-ups test waits with a cheap text query instead of a longer timeout; the seed clears only the `e2e-test` workspace's channels.
- PR Screenshots: "Not applicable: no visible change".
