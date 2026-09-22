import { AxeBuilder } from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = { users: { email: string; password: string }[] }

test.describe('UI foundation', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
    const ownerIndex =
      Array.from(testInfo.title).reduce(
        (sum, character) => sum + character.charCodeAt(0),
        0,
      ) % 5
    await page.goto('/sign-in')
    await page
      .getByRole('textbox', { name: 'Email' })
      .fill(seed.users[ownerIndex].email)
    await page.getByLabel('Password').fill(seed.users[0].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
  })

  test('shell at desktop width', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await expect(
      page.getByRole('heading', { name: /Inbox is ready/ }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
    await expect(page).toHaveScreenshot('shell-desktop.png', { fullPage: true })
  })

  test('shell at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/inbox')
    await expect(
      page.getByRole('navigation', { name: 'Primary navigation' }),
    ).toBeVisible()
    await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible()
    await expect(page).toHaveScreenshot('shell-mobile.png', { fullPage: true })
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
    await expect(page.locator('main')).toHaveScreenshot('gallery-desktop.png')
  })

  test('gallery at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/dev/ui')
    await expect(
      page.getByRole('heading', { name: 'TanStack Query pattern' }),
    ).toBeVisible()
    await expect(page.locator('main')).toHaveScreenshot('gallery-mobile.png')
  })

  test('shell is keyboard navigable', async ({ page }) => {
    await page.goto('/inbox')
    const problems = page.getByRole('link', { name: 'Problems' }).first()
    await problems.focus()
    await expect(problems).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/problems$/)
  })

  test('shell has no axe violations', async ({ page }) => {
    await page.goto('/inbox')
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
})
