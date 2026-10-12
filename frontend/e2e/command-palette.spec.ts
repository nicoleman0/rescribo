import { expect, test, type Page } from '@playwright/test'
import { axeViolations } from './axe.js'
import { saveSeedSession, seedSessionPath } from './seed-session.js'
import { expectTouchTarget } from './touch-target.js'

const sessionPath = seedSessionPath('command-palette')
// Owner of the e2e workspace, whose credentials no spec changes.
const OWNER = 2
const marker = `Palette ${Date.now()}`
const reportTitle = `${marker} report`
const problemTitle = `${marker} problem`

// Axe needs settled colours rather than a frame from the dialog fade.
test.use({ reducedMotion: 'reduce', storageState: sessionPath })

test.beforeAll(async ({ browser }, info) => {
  await saveSeedSession(browser, info.project.use.baseURL, sessionPath, OWNER)
  const context = await browser.newContext({
    baseURL: info.project.use.baseURL,
    storageState: sessionPath,
  })
  const page = await context.newPage()
  try {
    await page.goto('/inbox/new')
    await page.getByLabel('Title').fill(reportTitle)
    await page.getByLabel('Customer organisation').fill('Palette Customer')
    await page.getByRole('button', { name: 'Create report' }).click()
    await expect(
      page
        .getByRole('region', { name: 'Report detail' })
        .getByRole('heading', { name: reportTitle }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Create problem' }).click()
    await page.getByLabel('Problem title').fill(problemTitle)
    await page.getByRole('button', { name: 'Create and link' }).click()
    await expect(
      page.getByRole('link', { name: problemTitle }).first(),
    ).toBeVisible()
  } finally {
    await context.close()
  }
})

const palette = (page: Page) =>
  page.getByRole('dialog', { name: 'Command palette' })

async function openWithKeys(page: Page) {
  await page.goto('/inbox')
  await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible()
  await page.keyboard.press('Control+k')
  await expect(palette(page)).toBeVisible()
}

test('goes to a screen from the keyboard', async ({ page }) => {
  await openWithKeys(page)
  await expect(palette(page).getByRole('combobox')).toBeFocused()
  await page.keyboard.type('prob')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/problems$/)
  await expect(palette(page)).toHaveCount(0)
})

test('opens a problem by title', async ({ page }) => {
  await openWithKeys(page)
  await page.keyboard.type(marker)
  await palette(page).getByRole('option', { name: problemTitle }).click()
  await expect(page).toHaveURL(/\/problems\/[0-9a-f-]+$/)
  await expect(
    page.getByRole('heading', { name: problemTitle }).first(),
  ).toBeVisible()
})

test('opens a report by title', async ({ page }) => {
  await openWithKeys(page)
  await page.keyboard.type(marker)
  await palette(page)
    .getByRole('option', { name: new RegExp(`${reportTitle}`) })
    .click()
  await expect(page).toHaveURL(/\/inbox\/[0-9a-f-]+$/)
  await expect(
    page
      .getByRole('region', { name: 'Report detail' })
      .getByRole('heading', { name: reportTitle }),
  ).toBeVisible()
})

test('changes the theme and Settings shows it', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' })
  await openWithKeys(page)
  await palette(page).getByRole('option', { name: 'Dark theme' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page
    .getByRole('link', { name: 'Settings', exact: true })
    .first()
    .click()
  await expect(
    page
      .getByRole('group', { name: 'Theme' })
      .getByRole('radio', { name: 'Dark' }),
  ).toBeChecked()
})

test('arrow keys and Enter run the third item', async ({ page }) => {
  await openWithKeys(page)
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  // Inbox, Problems, Follow-ups: the third screen.
  await expect(page).toHaveURL(/\/follow-ups$/)
})

for (const scheme of ['light', 'dark'] as const) {
  test(`open palette with results has no axe violations in ${scheme}`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: scheme })
    await openWithKeys(page)
    await page.keyboard.type(marker)
    await expect(
      palette(page).getByRole('option', { name: problemTitle }),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })
}

test('phone width keeps 44px targets and does not scroll sideways', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/inbox')
  const trigger = page.getByRole('button', { name: 'Open command palette' })
  await expectTouchTarget(trigger)
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true)
  await trigger.click()
  await expect(palette(page)).toBeVisible()
  await page.keyboard.type(marker)
  await expect(
    palette(page).getByRole('option', { name: problemTitle }),
  ).toBeVisible()
  for (const option of await palette(page).getByRole('option').all()) {
    await expectTouchTarget(option)
  }
  await expect(
    palette(page).getByText('Shortcuts', { exact: true }),
  ).toHaveCount(0)
  // The dialog's scroll lock removes the page scrollbar and pads for it, so
  // compare against the viewport rather than clientWidth.
  const box = await palette(page).boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(390)
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true)
})

test('has no running animation under reduced motion', async ({ page }) => {
  await openWithKeys(page)
  const running = await page.evaluate(() =>
    document
      .getAnimations()
      .filter(
        (animation) =>
          animation.effect instanceof KeyframeEffect &&
          animation.effect.target?.closest(
            '[data-slot="dialog-content"], [data-slot="dialog-overlay"]',
          ),
      )
      .map((animation) => animation.playState),
  )
  expect(running).toEqual([])
})
