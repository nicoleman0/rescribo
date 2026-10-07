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

test('the demo visitor sees labelled, simulated data', async ({ page }) => {
  await signInAsVisitor(page)
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
})
