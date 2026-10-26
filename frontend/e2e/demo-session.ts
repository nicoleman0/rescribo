import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { authDir, saveSession, signIn } from './session.js'
import { expect, type Browser, type Page } from '@playwright/test'

const demoPath = path.join(authDir, 'demo.json')

async function demoCredentials() {
  return JSON.parse(await readFile(demoPath, 'utf8')) as {
    email: string
    password: string
  }
}

// Login is throttled per identity, so demo specs sign in once in beforeAll
// and reuse the saved session instead of signing in per test.
export async function signInAsDemo(page: Page) {
  await signIn(page, await demoCredentials())
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
  await saveSession(browser, baseURL, sessionPath, await demoCredentials())
}

export async function openDemoInbox(page: Page) {
  // A dead saved session redirects to /sign-in; fail at the start of the test.
  await page.goto('/inbox')
  await expect(page).toHaveURL(/\/inbox$/)
}
