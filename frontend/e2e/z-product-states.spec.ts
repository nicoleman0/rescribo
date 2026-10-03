import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = {
  users: { email: string; password: string }[]
  workspace_id: string
  expired_invitation_token: string
}
type PageOfIds = { results: { id: string }[] }

async function signIn(page: Page, seed: Seed) {
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[1].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
}

test('product routes fit narrow screens, accept keyboard entry, and pass axe', async ({
  page,
}) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await signIn(page, seed)
  const reports = await page.request.get(
    `/api/workspaces/${seed.workspace_id}/reports/`,
  )
  const problems = await page.request.get(
    `/api/workspaces/${seed.workspace_id}/problems/`,
  )
  const followUps = await page.request.get(
    `/api/workspaces/${seed.workspace_id}/follow-ups/`,
  )
  const reportIds = (await reports.json()) as PageOfIds
  const problemIds = (await problems.json()) as PageOfIds
  const followUpIds = (await followUps.json()) as PageOfIds
  const routes = [
    '/inbox',
    '/inbox/new',
    '/problems',
    '/follow-ups',
    '/settings',
    ...(reportIds.results[0] ? [`/inbox/${reportIds.results[0].id}`] : []),
    ...(problemIds.results[0] ? [`/problems/${problemIds.results[0].id}`] : []),
    ...(followUpIds.results[0]
      ? [`/follow-ups/${followUpIds.results[0].id}`]
      : []),
    '/invite/unknown-token',
  ]

  for (const width of [375, 320]) {
    await page.setViewportSize({ width, height: 740 })
    for (const route of routes) {
      await page.goto(route)
      await page.waitForLoadState('networkidle')
      await expect(page.locator('main')).toBeVisible()
      await page.keyboard.press('Tab')
      expect(
        await page.evaluate('document.activeElement !== document.body'),
        `${route} at ${width}px should accept keyboard focus`,
      ).toBe(true)
      expect(
        await page.evaluate(
          'document.documentElement.scrollWidth <= innerWidth',
        ),
        `${route} at ${width}px should not overflow horizontally`,
      ).toBe(true)
      if (width === 320) expect(await axeViolations(page), route).toEqual([])
    }
  }
})
