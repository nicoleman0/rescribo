import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, type Browser, type Page } from '@playwright/test'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const demoPath = path.join(authDir, 'demo.json')

// Login is throttled per identity, so demo specs sign in once in beforeAll
// and reuse the saved session instead of signing in per test.
export async function signInAsDemo(page: Page) {
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

// test.use reads the storageState path at module load, before beforeAll runs.
export function demoSessionPath(name: string) {
  return path.join(authDir, `demo-${name}.json`)
}

export async function saveDemoSession(
  browser: Browser,
  baseURL: string | undefined,
  sessionPath: string,
) {
  // Start signed out; a stale file from an earlier run must not be loaded.
  const page = await browser.newPage({
    baseURL,
    storageState: { cookies: [], origins: [] },
  })
  await signInAsDemo(page)
  await page.context().storageState({ path: sessionPath })
  await page.close()
}

export async function openDemoInbox(page: Page) {
  // A dead saved session redirects to /sign-in; fail at the start of the test.
  await page.goto('/inbox')
  await expect(page).toHaveURL(/\/inbox$/)
}
