import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

const demoPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/demo.json',
)

async function signInAsVisitor(page: Page) {
  const demo = JSON.parse(await readFile(demoPath, 'utf8')) as {
    email: string
    password: string
  }
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(demo.email)
  await page.getByLabel('Password').fill(demo.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
}

const html = (page: Page) => page.locator('html')

test.describe('Themes', () => {
  test('a dark choice persists across reload and sign-out', async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: 'light' })
    await signInAsVisitor(page)
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

    await page.getByRole('button', { name: 'Sign out' }).first().click()
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
    await signInAsVisitor(page)
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
})
