import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { authDir, saveSession } from './session.js'
import type { Browser } from '@playwright/test'

const seedPath = path.join(authDir, 'seed.json')

type Seed = {
  users: { email: string; password: string }[]
  workspace_id: string
}

// test.use reads the storageState path at module load, before beforeAll runs.
export function seedSessionPath(name: string) {
  return path.join(authDir, `seed-${name}.json`)
}

export async function readSeed() {
  return JSON.parse(await readFile(seedPath, 'utf8')) as Seed
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
