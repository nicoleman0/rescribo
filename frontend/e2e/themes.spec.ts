import { expect, test, type Page } from '@playwright/test'
import { axeViolations } from './axe.js'
import { signInAsDemo } from './demo-session.js'
import { signOut } from './shell.js'

const html = (page: Page) => page.locator('html')

test.describe('Themes', () => {
  // No saved session here: the sign-out test would end it for the next test.
  test('a dark choice persists across reload and sign-out', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await signInAsDemo(page)
    await page.goto('/settings')
    const theme = page.getByRole('group', { name: 'Theme' })
    await expect(theme.getByRole('radio', { name: 'System' })).toBeChecked()
    await theme.getByText('Dark').click()
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')

    // With the app bundle blocked, only the index.html boot script can set the theme.
    await page.route('**/src/main.tsx*', (route) => route.abort())
    await page.reload()
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')
    await page.unroute('**/src/main.tsx*')
    await page.reload()
    await expect(theme.getByRole('radio', { name: 'Dark' })).toBeChecked()

    await signOut(page)
    await expect(page).toHaveURL(/\/sign-in$/)
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')
  })

  test('system follows the colour scheme without a reload', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await page.goto('/sign-in')
    await expect(html(page)).toHaveAttribute('data-theme', 'light')
    await page.emulateMedia({ colorScheme: 'dark' })
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')
  })

  test('dark screens have no axe violations', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' })
    await signInAsDemo(page)
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')
    await expect(
      page.getByRole('list', { name: 'Reports' }).getByRole('link').first(),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])

    await page.goto('/problems')
    await page
      .getByRole('link', { name: /Password reset emails/ })
      .first()
      .click()
    await expect(
      page.getByRole('heading', { name: 'Linked reports' }),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])

    await page.goto('/follow-ups')
    await expect(
      page.getByRole('list', { name: 'Follow-ups' }).getByRole('link').first(),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])

    await page.goto('/settings')
    await expect(page.getByRole('group', { name: 'Theme' })).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
  })

  test('a forest choice persists across reload and sign-out', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await signInAsDemo(page)
    await page.goto('/settings')
    const palette = page.getByRole('group', { name: 'Palette' })
    await expect(palette.getByRole('radio', { name: 'Indigo' })).toBeChecked()
    await palette.getByText('Forest').click()
    await expect(html(page)).toHaveAttribute('data-palette', 'forest')

    // With the app bundle blocked, only the index.html boot script can set the palette.
    await page.route('**/src/main.tsx*', (route) => route.abort())
    await page.reload()
    await expect(html(page)).toHaveAttribute('data-palette', 'forest')
    await page.unroute('**/src/main.tsx*')
    await page.reload()
    await expect(palette.getByRole('radio', { name: 'Forest' })).toBeChecked()

    await signOut(page)
    await expect(page).toHaveURL(/\/sign-in$/)
    await expect(html(page)).toHaveAttribute('data-palette', 'forest')
  })

  test('autumn keeps its palette when the theme switches to dark', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await signInAsDemo(page)
    await page.goto('/settings')
    const palette = page.getByRole('group', { name: 'Palette' })
    await palette.getByText('Autumn').click()
    await page.getByRole('group', { name: 'Theme' }).getByText('Dark').click()
    await expect(html(page)).toHaveAttribute('data-theme', 'dark')
    await expect(html(page)).toHaveAttribute('data-palette', 'autumn')
    await expect(palette.getByRole('radio', { name: 'Autumn' })).toBeChecked()
  })

  test('a status badge paints the same in indigo and forest', async ({
    page,
  }) => {
    await signInAsDemo(page)
    const badge = page.locator('[data-slot="status-badge"]').first()
    const paint = () =>
      badge.evaluate((element) => {
        const style = getComputedStyle(element)
        const dot = getComputedStyle(element.firstElementChild!)
        return [style.backgroundColor, style.color, dot.backgroundColor]
      })
    await expect(badge).toBeVisible()
    const indigo = await paint()

    await page.evaluate(() =>
      localStorage.setItem('rescribo-palette', 'forest'),
    )
    await page.reload()
    await expect(html(page)).toHaveAttribute('data-palette', 'forest')
    await expect(badge).toBeVisible()
    expect(await paint()).toEqual(indigo)
  })

  for (const theme of ['light', 'dark'] as const) {
    test(`settings in forest ${theme} has no axe violations`, async ({
      page,
    }) => {
      await page.emulateMedia({ colorScheme: theme })
      await signInAsDemo(page)
      await page.evaluate(() =>
        localStorage.setItem('rescribo-palette', 'forest'),
      )
      await page.goto('/settings')
      await expect(html(page)).toHaveAttribute('data-palette', 'forest')
      await expect(html(page)).toHaveAttribute('data-theme', theme)
      await expect(page.getByRole('group', { name: 'Palette' })).toBeVisible()
      expect(await axeViolations(page)).toEqual([])
    })
  }
})
