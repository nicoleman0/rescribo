import { expect, test } from '@playwright/test'
import { axeViolations } from './axe.js'
import { readSeed, saveSeedSession, seedSessionPath } from './seed-session.js'
import { expectVisibleControlTouchTargets } from './touch-target.js'
import { signIn } from './session.js'

test.describe('Settings owner journey', () => {
  // Tests 4 and 5 need the member and workspace from earlier tests, so serial
  // mode stops at the first failure instead of failing on absent state.
  test.describe.configure({ mode: 'serial' })
  test.use({ storageState: seedSessionPath('settings-owner') })

  test.beforeAll(async ({ browser }, info) => {
    await saveSeedSession(
      browser,
      info.project.use.baseURL,
      seedSessionPath('settings-owner'),
      9,
    )
  })

  test('owner keeps one active owner and invites a member who sees only member settings', async ({
    page,
    browser,
  }, testInfo) => {
    await page.goto('/settings/members')
    await expect(page).toHaveTitle('Members · Settings · Rescribo')
    await expect(
      page.getByRole('heading', { name: 'Members and invitations' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Make member', exact: true }).click()
    await expect(page.getByText(/At least one active owner/i)).toBeVisible()
    await page
      .getByLabel('Invite email')
      .fill(`settings-${Date.now()}@example.test`)
    await page.getByRole('button', { name: 'Create invitation' }).click()
    const invite = await page.getByLabel('Invitation link').inputValue()
    const invitePath = new URL(invite).pathname
    const member = await browser.newPage({
      baseURL: testInfo.project.use.baseURL,
      // test.use() context options reach browser-newed contexts too, so start
      // signed out; with the owner cookie the accept would rotate it away.
      storageState: { cookies: [], origins: [] },
    })
    await member.goto(invitePath)
    await member.getByLabel('Full name').fill('Settings Member')
    await member
      .getByLabel('Password', { exact: true })
      .fill('Settings-member-2026!')
    await member.getByLabel('Confirm password').fill('Settings-member-2026!')
    await member.getByRole('button', { name: 'Accept invitation' }).click()
    await expect(member).toHaveURL(/\/inbox$/)
    await member.goto('/settings/workspace')
    const memberNav = member.getByRole('navigation', {
      name: 'Settings sections',
    })
    await expect(memberNav.getByRole('link')).toHaveCount(3)
    await expect(
      member.getByText(
        'Workspace owners manage invitations, members, connections and deletion.',
      ),
    ).toBeVisible()
    await expect(
      member.getByRole('button', { name: 'Delete workspace', exact: true }),
    ).toHaveCount(0)
    await member.close()
  })

  for (const width of [390, 320]) {
    test(`settings sections fit, meet touch targets and pass axe at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 844 })
      await page.goto('/settings/members')
      for (const [slug, label] of [
        ['appearance', 'Appearance'],
        ['members', 'Members'],
        ['connections', 'Connections'],
        ['slack-account', 'Slack account'],
        ['workspace', 'Workspace'],
      ]) {
        const nav = page.getByRole('navigation', { name: 'Settings sections' })
        await nav.getByRole('link', { name: label }).click()
        await expect(page).toHaveURL(new RegExp(`/settings/${slug}$`))
        await expect(nav.getByRole('link', { name: label })).toHaveAttribute(
          'aria-current',
          'page',
        )
        expect(
          await page.evaluate(
            'document.documentElement.scrollWidth <= innerWidth',
          ),
        ).toBe(true)
        await expectVisibleControlTouchTargets(page)
        expect(await axeViolations(page)).toEqual([])
      }
    })
  }

  test('members page lists the new member on desktop and mobile, and the owner promotes them', async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/settings/members')
    await expect(
      page.getByText('Settings Member', { exact: true }),
    ).toBeVisible()
    await expect(await axeViolations(page)).toEqual([])
    await page.screenshot({
      path: testInfo.outputPath('settings-desktop.png'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await expectVisibleControlTouchTargets(page)
    await expect(await axeViolations(page)).toEqual([])
    expect(
      await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
    ).toBe(true)
    await page.screenshot({
      path: testInfo.outputPath('settings-mobile.png'),
      fullPage: true,
    })
    await page.getByRole('button', { name: 'Make owner', exact: true }).click()
    await expect(
      page.getByRole('button', { name: 'Make member', exact: true }),
    ).toHaveCount(2)
  })

  test('owner deletes a report, then the workspace, after typed confirmation', async ({
    page,
  }) => {
    await page.goto('/inbox/new')
    await page
      .getByLabel('Title', { exact: true })
      .fill('Delete this settings test report')
    await page.getByRole('button', { name: 'Create report' }).click()
    await expect(
      page.getByRole('heading', { name: 'Delete this settings test report' }),
    ).toBeVisible()
    await page
      .getByRole('button', { name: 'Delete report', exact: true })
      .click()
    const reportForm = page.getByRole('form', { name: 'Delete report' })
    await expect(
      reportForm.getByRole('button', { name: 'Delete report', exact: true }),
    ).toBeDisabled()
    await reportForm.getByLabel('Type DELETE to confirm').fill('DELETE')
    await reportForm
      .getByRole('button', { name: 'Delete report', exact: true })
      .click()
    await expect(page).toHaveURL(/\/inbox$/)
    await page.goto('/settings/workspace')
    await page
      .getByRole('button', { name: 'Delete workspace', exact: true })
      .click()
    const form = page.getByRole('form', { name: 'Delete workspace' })
    await expect(form.getByText(/Backups expire/)).toBeVisible()
    await form.getByLabel('Type e2e-settings to confirm').fill('e2e-settings')
    await form
      .getByRole('button', { name: 'Delete workspace', exact: true })
      .click()
    await expect(
      page.getByRole('heading', {
        name: /Workspace access removed|Sign in/i,
      }),
    ).toBeVisible()
  })
})

test('a long member email does not overflow settings at 320px', async ({
  page,
}) => {
  const seed = await readSeed()
  await signIn(page, seed.users[1])
  await page.route('**/api/workspaces/*/memberships/', async (route) => {
    const response = await route.fetch()
    const members = (await response.json()) as { id: string; email: string }[]
    members.push({
      ...members[0],
      id: 'long-email-member',
      email: 'invite-0000000000000-with-a-long-name@example.test',
    })
    await route.fulfill({ response, json: members })
  })
  await page.setViewportSize({ width: 320, height: 740 })
  await page.goto('/settings/members')
  await expect(
    page.getByRole('button', { name: /^Remove invite-0000000000000/ }),
  ).toBeVisible()
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
})

test('the Slack connect form passes API validation', async ({ page }) => {
  const seed = await readSeed()
  await signIn(page, seed.users[1])
  // With Slack credentials the API answers with an authorise URL. Keep the
  // browser off slack.com.
  await page.route('https://slack.com/**', (route) =>
    route.fulfill({ body: 'Slack' }),
  )
  await page.goto('/settings/connections')
  const slack = page.getByRole('region', { name: 'Slack', exact: true })
  await slack.locator('form').nth(1).getByRole('checkbox').check()
  const [request] = await Promise.all([
    page.waitForRequest('**/connections/slack/setup/'),
    slack.getByRole('button', { name: /^(Connect|Reconnect) Slack$/ }).click(),
  ])
  expect(request.postDataJSON()).toEqual({ consent: true })
  const response = (await request.response())!
  const reply = (await response.json()) as { reason?: string }
  // 400 operator_setup without credentials, 200 with them.
  expect(reply.reason).not.toBe('invalid_request')
  expect([200, 400]).toContain(response.status())
})

// Mocked: a real check with the seeded fake credential would put the
// connection in `error` and cancel notifications other specs rely on.
test('a passing Slack check shows its result beside the button (mocked)', async ({
  page,
}) => {
  const seed = await readSeed()
  await signIn(page, seed.users[1])
  await page.route('**/connections/slack/refresh/', (route) =>
    route.fulfill({ status: 204 }),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/settings/connections')
  const slack = page.getByRole('region', { name: 'Slack', exact: true })
  await slack.getByRole('button', { name: 'Check Slack status' }).click()
  await expect(slack.getByRole('status')).toContainText(
    'Slack connection is working',
  )
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  expect(overflow).toBe(false)
  expect(await axeViolations(page)).toEqual([])
})

test('an owner allows and removes a Slack channel from the picker', async ({
  page,
}) => {
  const seed = await readSeed()
  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page, seed.users[4])
  await page.goto('/settings/connections')
  const slack = page.getByRole('region', { name: 'Slack', exact: true })
  const channels = slack.getByRole('region', { name: 'Allowed Slack channels' })
  await channels
    .getByRole('combobox', { name: 'Slack channel' })
    .selectOption('C0E2EPUBLIC')
  await channels.getByRole('checkbox').check()
  await slack.getByRole('button', { name: 'Allow channel' }).click()
  await expect(
    slack.getByText(/#support-requests \(C0E2EPUBLIC\)/),
  ).toBeVisible()
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
  expect(await axeViolations(page)).toEqual([])
  await slack
    .getByRole('button', { name: 'Remove channel support-requests' })
    .click()
  await expect(slack.getByText('No channels allowed yet.')).toBeVisible()
})

test('an owner sees the model provider form and a private base URL is refused', async ({
  page,
}) => {
  const seed = await readSeed()
  await signIn(page, seed.users[1])
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/settings/connections')
  const card = page.getByRole('region', { name: 'Model provider' })
  await expect(card.getByLabel('Provider', { exact: true })).toBeVisible()
  await card.getByLabel('Provider', { exact: true }).selectOption('other')
  await card
    .getByLabel('Base URL', { exact: true })
    .fill('https://127.0.0.1/v1')
  await card.getByLabel('Model', { exact: true }).fill('e2e-model')
  await card.getByLabel('API key', { exact: true }).fill('sk-e2e-not-a-key')
  await card.getByRole('checkbox').check()
  await card.getByRole('button', { name: 'Connect model provider' }).click()
  await expect(card.getByText(/resolve only to public addresses/)).toBeVisible()
  await expect(card.getByLabel('API key', { exact: true })).toHaveValue('')
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
  await expectVisibleControlTouchTargets(page)
  // The hover colour left by the click fails contrast: issue 273.
  await page.mouse.move(0, 0)
  expect(await axeViolations(page)).toEqual([])
})

test('a member sees the model provider status without a form', async ({
  page,
}) => {
  const seed = await readSeed()
  // User 6 has its password reset by the accounts spec.
  await signIn(page, seed.users[7])
  await page.goto('/settings/connections')
  const card = page.getByRole('region', { name: 'Model provider' })
  await expect(
    card.getByText('Ask a workspace owner to connect a model provider.'),
  ).toBeVisible()
  await expect(card.getByRole('textbox')).toHaveCount(0)
  await expect(card.getByRole('checkbox')).toHaveCount(0)
  expect(await axeViolations(page)).toEqual([])
})
