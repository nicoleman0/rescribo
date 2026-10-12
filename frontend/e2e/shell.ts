import type { Page } from '@playwright/test'

export async function signOut(page: Page) {
  await page.getByRole('button', { name: /User menu for/ }).click()
  await page.getByRole('menuitem', { name: 'Sign out' }).click()
}
