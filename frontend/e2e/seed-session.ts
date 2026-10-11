import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, type Browser } from '@playwright/test'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const seedPath = path.join(authDir, 'seed.json')

type Seed = {
  users: { email: string; password: string }[]
  workspace_id: string
}

// test.use reads the storageState path at module load, before beforeAll runs.
export function seedSessionPath(name: string) {
  return path.join(authDir, `seed-${name}.json`)
}

export async function saveSeedSession(
  browser: Browser,
  baseURL: string | undefined,
  sessionPath: string,
) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  const page = await browser.newPage({
    baseURL,
    storageState: { cookies: [], origins: [] },
  })
  try {
    await page.goto('/sign-in')
    await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[1].email)
    await page.getByLabel('Password').fill(seed.users[1].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
    await mkdir(path.dirname(sessionPath), { recursive: true })
    await page.context().storageState({ path: sessionPath })
  } finally {
    await page.close()
  }
  return seed
}
