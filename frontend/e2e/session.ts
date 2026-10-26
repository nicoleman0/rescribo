import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, type Browser, type Page } from '@playwright/test'

export const authDir = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth',
)

export type Credentials = { email: string; password: string }

// Login is throttled per identity and address, so these steps live in one
// place and every helper signs in exactly once per session file.
export async function signIn(page: Page, credentials: Credentials) {
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(credentials.email)
  await page.getByLabel('Password').fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
}

// Start signed out; a stale file from an earlier run must not be loaded,
// and test.use would otherwise load the file being created.
export async function saveSession(
  browser: Browser,
  baseURL: string | undefined,
  sessionPath: string,
  credentials: Credentials,
) {
  const page = await browser.newPage({
    baseURL,
    storageState: { cookies: [], origins: [] },
  })
  try {
    await signIn(page, credentials)
    await mkdir(path.dirname(sessionPath), { recursive: true })
    await page.context().storageState({ path: sessionPath })
  } finally {
    await page.close()
  }
}
