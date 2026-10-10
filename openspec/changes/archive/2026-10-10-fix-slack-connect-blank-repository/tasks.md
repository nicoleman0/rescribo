# Tasks

Delivers #145. Bug fix; `skip_specs: true`. Change only the files named below. Do not touch the backend or `frontend/openapi.yaml`.

Write the tests first (groups 1 and 2) and see them fail, then make the fix (group 3).

## 1. Component tests in `frontend/src/features/settings/settings-page.test.tsx`

Add everything at the end of the file. Reuse the existing `base`, `unlinked`, `render`, `slackConnection`, and the existing `afterEach`. Do not change existing tests.

- [x] 1.1 Add the two helpers. Use this code:

  ```tsx
  // Answers as the API does with no OAuth application configured, so the
  // form does not navigate away.
  function ownerWithSetup(provider: 'slack' | 'github', connections: unknown[]) {
    testMembership.role = 'owner'
    return stubApi({
      ...unlinked,
      [`GET ${base}connections/`]: () => json(connections),
      [`GET ${base}memberships/`]: () => json([]),
      [`GET ${base}invitations/`]: () => json([]),
      [`POST ${base}connections/${provider}/setup/`]: () =>
        json(
          {
            detail: 'Ask the operator.',
            reason: 'operator_setup',
            field_errors: {},
          },
          400,
        ),
    })
  }
  function setupBodies(fetch: ReturnType<typeof stubApi>) {
    return fetch.mock.calls
      .filter(([input]) => String(input).endsWith('/setup/'))
      .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
  }
  ```

- [x] 1.2 Add the Slack tests (first connect and reconnect). Use this code:

  ```tsx
  test.each([
    ['Connect Slack', []],
    ['Reconnect Slack', [slackConnection]],
  ])('%s sends consent without a repository', async (button, connections) => {
    const fetch = ownerWithSetup('slack', connections)
    render()
    const slack = await screen.findByRole('region', { name: 'Slack' })
    const user = userEvent.setup()
    await user.click(within(slack).getByRole('checkbox'))
    await user.click(within(slack).getByRole('button', { name: button }))
    expect(await within(slack).findByText('Ask the operator.')).toBeVisible()
    expect(setupBodies(fetch)).toEqual([{ consent: true }])
  })
  ```

- [x] 1.3 Add the GitHub test. Use this code:

  ```tsx
  test('Connect GitHub sends the repository with consent', async () => {
    const fetch = ownerWithSetup('github', [])
    render()
    const github = await screen.findByRole('region', { name: 'GitHub' })
    const user = userEvent.setup()
    await user.type(
      within(github).getByLabelText('GitHub repository'),
      'acme/web',
    )
    await user.click(within(github).getByRole('checkbox'))
    await user.click(
      within(github).getByRole('button', { name: 'Connect GitHub' }),
    )
    expect(await within(github).findByText('Ask the operator.')).toBeVisible()
    expect(setupBodies(fetch)).toEqual([
      { repository: 'acme/web', consent: true },
    ])
  })
  ```

- [x] 1.4 Run `cd frontend && npx vitest run src/features/settings/settings-page.test.tsx`. Verify: the two Slack tests fail with `+ "repository": ""`, and every other test passes. Run `npx prettier --check src/features/settings/settings-page.test.tsx` and fix formatting with `--write` if it warns.

## 2. Browser test in `frontend/e2e/settings.spec.ts`

- [x] 2.1 Add this test at the end of the file. Do not change existing tests.

  ```ts
  test('the Slack connect form passes API validation', async ({ page }) => {
    const seed = JSON.parse(
      await readFile(path.join(authDir, 'seed.json'), 'utf8'),
    ) as { users: { email: string; password: string }[] }
    await page.goto('/sign-in')
    await page.getByLabel('Email').fill(seed.users[1].email)
    await page.getByLabel('Password').fill(seed.users[0].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
    // With Slack credentials the API answers with an authorise URL. Keep the
    // browser off slack.com.
    await page.route('https://slack.com/**', (route) =>
      route.fulfill({ body: 'Slack' }),
    )
    await page.goto('/settings')
    const slack = page.getByRole('region', { name: 'Slack', exact: true })
    await slack.getByRole('checkbox').check()
    const [request] = await Promise.all([
      page.waitForRequest('**/connections/slack/setup/'),
      slack
        .getByRole('button', { name: /^(Connect|Reconnect) Slack$/ })
        .click(),
    ])
    expect(request.postDataJSON()).toEqual({ consent: true })
    const response = (await request.response())!
    const reply = (await response.json()) as { reason?: string }
    // 400 operator_setup without credentials, 200 with them.
    expect(reply.reason).not.toBe('invalid_request')
    expect([200, 400]).toContain(response.status())
  })
  ```

- [x] 2.2 Run `cd frontend && RESCRIBO_E2E_API_PORT=8145 RESCRIBO_E2E_FRONTEND_PORT=5145 npx playwright test e2e/settings.spec.ts -g "Slack connect form"`. Verify: the new test fails on `+ "repository": ""`. Both variables are required; without them Playwright tests another checkout.

## 3. Fix in `frontend/src/features/settings/connection-settings.tsx`

- [x] 3.1 In the setup form's `onSubmit`, replace `body: { repository, consent },` with:

  ```tsx
  // The API rejects a blank repository, and Slack has none.
  body:
    provider === 'github'
      ? { repository, consent }
      : { consent },
  ```

  Leave the rest of the file unchanged, including the `repository` state and the channel form. Verify: `git diff frontend/src/features/settings/connection-settings.tsx` shows only this hunk, and `cd frontend && npx prettier --check src/features/settings/connection-settings.tsx` passes.
- [x] 3.2 Rerun 1.4. Verify: every test in the file passes, including the three new ones.
- [x] 3.3 Rerun 2.2. Verify: 1 passed (plus setup).

## 4. Repository checks

- [x] 4.1 `npx @fission-ai/openspec validate --all --strict` passes.
- [x] 4.2 `task check test build schema-check` passes with PostgreSQL and Redis running (see `.claude/brief.md` for the ports; do not start or stop services). Record the test counts for the PR. `schema-check` must report no API change.
- [x] 4.3 `RESCRIBO_E2E_API_PORT=8145 RESCRIBO_E2E_FRONTEND_PORT=5145 task e2e` passes. Record the counts for the PR.
- [x] 4.4 No dev server is left on 8145 or 5145.

## Workflow follow-up

- Archive this change in the PR that completes #145 (`/opsx:archive`).
- PR milestone: none.
- PR "Decisions to review": the Slack card cannot show an error for a field it does not render (out of scope here), and the browser test's reply check accepts 200 or 400.
- PR Screenshots: "Not applicable: no visible change".
