import { AxeBuilder } from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { demoSessionPath, saveDemoSession } from './demo-session.js'
import { signOut } from './shell.js'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const seedPath = path.join(authDir, 'seed.json')
const ownerSessionPath = path.join(authDir, 'ui-foundation.json')
const demoPath = demoSessionPath('shell')
type Seed = { users: { email: string; password: string }[] }

// Axe needs settled colours rather than a frame from the page fade.
test.use({ reducedMotion: 'reduce', storageState: ownerSessionPath })

async function waitForAnimations(page: import('@playwright/test').Page) {
  await page.evaluate(async () => {
    await Promise.all(
      document
        .getAnimations()
        .map((animation) => animation.finished.catch(() => undefined)),
    )
  })
}

test.describe('UI foundation', () => {
  test.beforeAll(async ({ browser }, info) => {
    const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
    const ownerIndex = 8
    const context = await browser.newContext({
      baseURL: info.project.use.baseURL,
      storageState: { cookies: [], origins: [] },
    })
    const page = await context.newPage()
    await page.goto('/sign-in')
    await page
      .getByRole('textbox', { name: 'Email' })
      .fill(seed.users[ownerIndex].email)
    await page.getByLabel('Password').fill(seed.users[0].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
    await context.storageState({ path: ownerSessionPath })
    await context.close()
  })

  test('shell at desktop width', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/follow-ups')
    await expect(
      page.getByRole('heading', { name: 'Follow-ups' }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
  })

  test('phone user menu has a 44px target and no horizontal scroll', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/inbox')
    const trigger = page.getByRole('button', { name: /User menu for/ })
    const box = await trigger.boundingBox()
    expect(box?.height).toBeGreaterThanOrEqual(44)
    await trigger.click()
    expect(
      await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
    ).toBe(true)
  })

  test('shell at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/follow-ups')
    await expect(
      page.getByRole('navigation', { name: 'Primary navigation' }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
    expect(
      await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
    ).toBe(true)
  })

  test('gallery at desktop width', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/dev/ui')
    await expect(
      page.getByRole('heading', { name: 'UI gallery' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Loading state' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Error and retry states' }),
    ).toBeVisible()
  })

  test('gallery at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/dev/ui')
    await expect(
      page.getByRole('heading', { name: 'TanStack Query pattern' }),
    ).toBeVisible()
    expect(
      await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
    ).toBe(true)
  })

  test('shell is keyboard navigable', async ({ page }) => {
    await page.goto('/inbox')
    const problems = page.getByRole('link', { name: 'Problems' }).first()
    await problems.focus()
    await expect(problems).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/problems$/)
  })

  test('skip link is the first tab stop on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible()
    const sidebar = page.locator('[data-slot="sidebar"]')
    const beforeFocus = await sidebar.boundingBox()
    expect(beforeFocus).not.toBeNull()
    await page.keyboard.press('Tab')
    await expect(
      page.getByRole('link', { name: 'Skip to main content' }),
    ).toBeFocused()
    expect(await sidebar.boundingBox()).toEqual(beforeFocus)
  })

  test('sign out is in view on settings without scrolling', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/settings')
    await expect(
      page.getByRole('heading', { name: 'Members and invitations' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /User menu for/ }),
    ).toBeInViewport()
  })

  test('shell has no axe violations', async ({ page }) => {
    await page.goto('/inbox')
    await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible()
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations).toEqual([])
  })

  test('gallery has no axe violations', async ({ page }) => {
    await page.goto('/dev/ui')
    await expect(
      page.getByRole('heading', { name: 'UI gallery' }),
    ).toBeVisible()
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations).toEqual([])
  })

  test('user menu signs out', async ({ page }) => {
    await page.goto('/inbox')
    await signOut(page)
    await expect(page).toHaveURL(/\/sign-in$/)
  })
})

test.describe('Demo shell', () => {
  test.use({ storageState: demoPath })

  test.beforeAll(async ({ browser }, info) =>
    saveDemoSession(browser, info.project.use.baseURL, demoPath),
  )

  test('collapsed rail persists and problem breadcrumb shows its title', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await page.getByRole('button', { name: 'Toggle Sidebar' }).click()
    await expect(
      page.locator('[data-slot="sidebar"][data-collapsible="icon"]'),
    ).toBeVisible()
    await page.reload()
    await expect(
      page.locator('[data-slot="sidebar"][data-collapsible="icon"]'),
    ).toBeVisible()
    await page.goto('/problems')
    const title = 'Password reset emails arrive after the link expires'
    await page
      .getByRole('link', { name: new RegExp(title) })
      .first()
      .click()
    await expect(
      page.getByRole('navigation', { name: 'Breadcrumb' }).getByText(title),
    ).toBeVisible()
    expect(
      await new AxeBuilder({ page })
        .analyze()
        .then((result) => result.violations),
    ).toEqual([])
    await page.getByRole('button', { name: /User menu for/ }).click()
    await waitForAnimations(page)
    expect(
      await new AxeBuilder({ page })
        .analyze()
        .then((result) => result.violations),
    ).toEqual([])
    await page.getByRole('menuitemradio', { name: 'Dark' }).click()
    await waitForAnimations(page)
    expect(
      await new AxeBuilder({ page })
        .analyze()
        .then((result) => result.violations),
    ).toEqual([])
    await page.getByRole('button', { name: /User menu for/ }).click()
    await waitForAnimations(page)
    expect(
      await new AxeBuilder({ page })
        .analyze()
        .then((result) => result.violations),
    ).toEqual([])
  })
})
