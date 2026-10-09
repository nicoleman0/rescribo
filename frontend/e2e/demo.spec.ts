import { expect, test } from '@playwright/test'
import { axeViolations } from './axe.js'
import {
  demoSessionPath,
  openDemoInbox,
  saveDemoSession,
} from './demo-session.js'

const sessionPath = demoSessionPath('demo')

test.beforeAll(async ({ browser }, info) =>
  saveDemoSession(browser, info.project.use.baseURL, sessionPath),
)
test.use({ storageState: sessionPath })

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

  await page.goto('/settings')
  await expect(
    page.getByRole('note').getByText('Integrations are disabled in the demo'),
  ).toBeVisible()
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
