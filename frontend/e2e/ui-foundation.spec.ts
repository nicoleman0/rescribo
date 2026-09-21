import { AxeBuilder } from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.describe('UI foundation', () => {
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
