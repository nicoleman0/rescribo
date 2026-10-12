import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { saveSeedSession, seedSessionPath } from './seed-session.js'
import { demoSessionPath, saveDemoSession } from './demo-session.js'
import { axeViolations } from './axe.js'
import { signOut } from './shell.js'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const seedPath = path.join(authDir, 'seed.json')
const sessionPath = seedSessionPath('ui-foundation')
const demoPath = demoSessionPath('shell')

// Axe needs settled colours rather than a frame from the page fade.
test.use({ reducedMotion: 'reduce' })

test.describe('UI foundation', () => {
  test.use({ storageState: sessionPath })

  test.beforeAll(async ({ browser }, info) => {
    await saveSeedSession(browser, info.project.use.baseURL, sessionPath, 8)
  })

  test('shell at desktop width', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/follow-ups')
    await expect(
      page.getByRole('heading', { name: 'Follow-ups' }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
  })

  test('active desktop destination has selected styling', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    const navigation = page.getByRole('navigation', {
      name: 'Primary navigation',
    })
    const inbox = navigation.getByRole('link', { name: 'Inbox', exact: true })
    const problems = navigation.getByRole('link', {
      name: 'Problems',
      exact: true,
    })
    await expect(inbox).toHaveAttribute('aria-current', 'page')
    const inboxColor = await inbox.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    const problemsColor = await problems.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    expect(inboxColor).not.toBe(problemsColor)
    const inboxBox = await inbox.boundingBox()
    const problemsBox = await problems.boundingBox()
    expect(inboxBox).not.toBeNull()
    expect(problemsBox).not.toBeNull()
    expect(problemsBox!.y - inboxBox!.y - inboxBox!.height).toBe(3)
  })

  test('phone Ctrl+B does not open a sidebar sheet', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/inbox')
    await page.keyboard.press('Control+b')
    await expect(page.locator('[data-slot="sheet-content"]')).toHaveCount(0)
    await expect(page.locator('[data-slot="sidebar"]')).toHaveCount(0)
  })

  test('sidebar divider uses the border token', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    const divider = page.locator('[data-slot="sidebar-container"]')
    const borderColor = await divider.evaluate(
      (el) => getComputedStyle(el).borderRightColor,
    )
    const headerBorder = await page
      .getByRole('banner')
      .evaluate((el) => getComputedStyle(el).borderBottomColor)
    expect(borderColor).toBe(headerBorder)
  })

  test('phone user menu has a 44px target and no horizontal scroll', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/inbox')
    const trigger = page.getByRole('button', { name: /User menu for/ })
    const box = await trigger.boundingBox()
    expect(box?.height).toBeGreaterThanOrEqual(44)
    expect(box?.width).toBeGreaterThanOrEqual(44)
    await trigger.click()
    const menu = page.getByRole('menu')
    const menuBackground = await menu.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    const alpha = menuBackground.match(/,\s*([\d.]+)\)$/)?.[1] ?? '1'
    expect(Number(alpha)).toBeGreaterThan(0)
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
    expect(await axeViolations(page)).toEqual([])
  })

  test('gallery has no axe violations', async ({ page }) => {
    await page.goto('/dev/ui')
    await expect(
      page.getByRole('heading', { name: 'UI gallery' }),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })

  test('user menu signs out', async ({ browser, baseURL }) => {
    const context = await browser.newContext({
      baseURL,
      storageState: { cookies: [], origins: [] },
    })
    const page = await context.newPage()
    try {
      await page.goto('/sign-in')
      const { users } = JSON.parse(await readFile(seedPath, 'utf8')) as {
        users: { email: string; password: string }[]
      }
      await page.getByRole('textbox', { name: 'Email' }).fill(users[8].email)
      await page.getByLabel('Password').fill(users[0].password)
      await page.getByRole('button', { name: 'Sign in' }).click()
      await expect(page).toHaveURL(/\/inbox$/)
      await page.goto('/inbox')
      await signOut(page)
      await expect(page).toHaveURL(/\/sign-in$/)
    } finally {
      await context.close()
    }
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
      page
        .getByRole('navigation', { name: 'Breadcrumb' })
        .getByRole('link', { name: 'Problems' }),
    ).toHaveAttribute('href', '/problems')
    await expect(
      page.getByRole('navigation', { name: 'Breadcrumb' }).getByText(title),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
    await page.getByRole('button', { name: /User menu for/ }).click()
    await expect(page.getByRole('menu')).toBeVisible()
    const menuViolations = await axeViolations(page)
    expect(menuViolations).toEqual([])
    await page.getByRole('menuitemradio', { name: 'Dark' }).click()
    expect(await axeViolations(page)).toEqual([])
    await page.getByRole('button', { name: /User menu for/ }).click()
    await expect(page.getByRole('menu')).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })

  test('collapsed rail keeps navigation counts visible', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await page.getByRole('button', { name: 'Toggle Sidebar' }).click()
    const badges = page.locator('[data-slot="sidebar-menu-badge"]')
    await expect(badges.first()).toBeVisible()
    await expect(badges.last()).toBeVisible()
    await expect(badges.first().locator('.sr-only')).toContainText(
      'new reports',
    )
    await expect(badges.last().locator('.sr-only')).toContainText(
      'follow-ups need approval',
    )
  })

  test('user menu surface has a background', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await page.getByRole('button', { name: /User menu for/ }).click()
    const menu = page.getByRole('menu')
    const background = await menu.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    )
    const alpha = background.match(/,\s*([\d.]+)\)$/)?.[1] ?? '1'
    expect(Number(alpha)).toBeGreaterThan(0)
  })
})
