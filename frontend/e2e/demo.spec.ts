import { expect, test } from '@playwright/test'
import { axeViolations } from './axe.js'
import {
  demoSessionPath,
  openDemoInbox,
  saveDemoSession,
} from './demo-session.js'
import { E2E_DEMO_PASSWORD } from './demo-password.js'
import { expectTouchTarget } from './touch-target.js'

const sessionPath = demoSessionPath('demo')

test.beforeAll(async ({ browser }, info) =>
  saveDemoSession(browser, info.project.use.baseURL, sessionPath),
)
test.use({ storageState: sessionPath })

test('a signed-out visitor uses the demo hint to open the demo inbox', async ({
  browser,
}, info) => {
  const context = await browser.newContext({
    baseURL: String(info.project.use.baseURL),
    storageState: { cookies: [], origins: [] },
  })
  const page = await context.newPage()
  await page.goto('/sign-in')
  await page.getByRole('button', { name: 'Use demo login' }).click()
  await expect(page.getByRole('textbox', { name: 'Email' })).toHaveValue(
    'demo@example.com',
  )
  await expect(page.getByLabel('Password')).toHaveValue(E2E_DEMO_PASSWORD)
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeFocused()
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await expect(page.getByLabel('Demo workspace')).toHaveText('Demo')
  await context.close()
})

test('the demo visitor sees labelled, simulated data', async ({ page }) => {
  await openDemoInbox(page)
  await expect(page.getByLabel('Demo workspace')).toHaveText('Demo')
  await expect(
    page
      .getByRole('list', { name: 'Reports' })
      .getByText('Search ignores accented names'),
  ).toBeVisible()
  expect(await axeViolations(page)).toEqual([])

  await page.goto('/follow-ups?bucket=completed')
  await expect(page.getByLabel('Demo workspace')).toBeVisible()
  await expect(page.getByText('Sent (simulated)').first()).toBeVisible()

  await page.goto('/settings/connections')
  await expect(
    page.getByRole('note').getByText('Integrations are disabled in the demo'),
  ).toBeVisible()
  await page.goto('/settings/workspace')
  await expect(
    page.getByRole('button', { name: 'Delete workspace' }),
  ).not.toBeVisible()

  // Rows animate in; measure them at rest.
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const title = 'Password reset emails arrive after the link expires'
  const row = page
    .getByRole('list', { name: 'Problems' })
    .getByRole('link', { name: new RegExp(title) })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/problems')
  await expect(row).toBeVisible()
  const rowBox = (await row.boundingBox())!
  const titleBox = (await row.getByText(title, { exact: true }).boundingBox())!
  expect(titleBox.width).toBeGreaterThan(rowBox.width * 0.6)
  for (const badge of [
    row.getByText('Needs review'),
    row.getByText('Fix available'),
    row.getByText(/^GitHub #\d+/),
  ]) {
    const box = (await badge.boundingBox())!
    expect(box.x + box.width).toBeLessThanOrEqual(rowBox.x + rowBox.width)
  }

  await page.setViewportSize({ width: 1280, height: 860 })
  const wideTitle = (await row.getByText(title, { exact: true }).boundingBox())!
  const wideBadge = (await row.getByText('Needs review').boundingBox())!
  // On desktop the badges share the title's first line.
  expect(wideBadge.y).toBeLessThan(wideTitle.y + wideTitle.height)
  expect(wideBadge.x).toBeGreaterThan(wideTitle.x + wideTitle.width)
})

test('standalone links on problem detail keep a phone touch target', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/problems')
  await page
    .getByRole('list', { name: 'Problems' })
    .getByRole('link', {
      name: /Password reset emails arrive after the link expires/,
    })
    .click()
  await expect(
    page.getByRole('heading', {
      name: 'Password reset emails arrive after the link expires',
    }),
  ).toBeVisible()

  const reports = page.getByRole('list', { name: 'Linked reports' })
  await expect(reports.getByRole('link').first()).toBeVisible()
  const titles = await reports.getByRole('link').all()
  expect(titles.length).toBeGreaterThan(1)
  for (const link of titles) await expectTouchTarget(link)

  const external = page.locator('a[target="_blank"]')
  expect(await external.count()).toBeGreaterThanOrEqual(2)
  for (const link of await external.all()) await expectTouchTarget(link)

  const summary = page
    .getByText(/linked 6 reports/)
    .locator('xpath=ancestor-or-self::summary')
  await expectTouchTarget(summary)
  await summary.click()
  const revealed = page.locator('details[open] ul a')
  expect(await revealed.count()).toBe(6)
  for (const link of await revealed.all()) await expectTouchTarget(link)

  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('the demo label stays visible with the sidebar collapsed', async ({
  page,
}) => {
  await openDemoInbox(page)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: 'Toggle Sidebar' }).click()
  await expect(page.getByLabel('Demo workspace')).toBeVisible()
})
