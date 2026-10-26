import { readFile } from 'node:fs/promises'
import path from 'node:path'
import type { Browser, Page } from '@playwright/test'
import { authDir, saveSession, signIn } from './session.js'

const seedPath = path.join(authDir, 'seed.json')

type Seed = {
  users: { email: string; password: string }[]
  workspace_id: string
  expired_invitation_token: string
}

// test.use reads the storageState path at module load, before beforeAll runs.
export function seedSessionPath(name: string) {
  return path.join(authDir, `seed-${name}.json`)
}

export async function readSeed() {
  return JSON.parse(await readFile(seedPath, 'utf8')) as Seed
}

export async function signInAsSeededOwner(page: Page) {
  const seed = await readSeed()
  // User 2 keeps fixed credentials while other specs change member passwords.
  await signIn(page, seed.users[2])
}

export async function saveSeedSession(
  browser: Browser,
  baseURL: string | undefined,
  sessionPath: string,
  userIndex = 1,
) {
  const seed = await readSeed()
  await saveSession(browser, baseURL, sessionPath, seed.users[userIndex])
  return seed
}
