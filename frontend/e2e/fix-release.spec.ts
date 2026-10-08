import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = { users: { email: string; password: string }[] }

async function signIn(page: Page) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[2].email)
  await page.getByLabel('Password').fill(seed.users[2].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
}

test('links, changes, and removes a release on a confirmed fix', async ({
  page,
}) => {
  let problem: Record<string, any> | undefined
  await page.route(
    '**/api/workspaces/*/problems/*/confirm-fix/',
    async (route) => {
      const response = await route.fetch()
      problem = await response.json()
      await route.fulfill({
        status: response.status(),
        contentType: 'application/json',
        body: JSON.stringify(problem),
      })
    },
  )
  await page.route('**/api/workspaces/*/problems/*/', async (route) => {
    if (!problem) return route.continue()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(problem),
    })
  })
  await page.route('**/api/workspaces/*/releases/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [
          {
            external_id: '101',
            tag_name: 'v4.13',
            name: '4.13',
            url: 'https://github.com/acme/widgets/releases/tag/v4.13',
            published_at: '2026-10-01T12:00:00Z',
            prerelease: false,
          },
          {
            external_id: '102',
            tag_name: 'v4.14-rc1',
            name: '4.14 preview',
            url: 'https://github.com/acme/widgets/releases/tag/v4.14-rc1',
            published_at: '2026-10-02T12:00:00Z',
            prerelease: true,
          },
        ],
        has_next: false,
      }),
    }),
  )
  await page.route(
    '**/api/workspaces/*/problems/*/fix-release/',
    async (route) => {
      if (route.request().method() !== 'POST') return route.continue()
      const selected = route.request().postDataJSON() as { external_id: string }
      if (!problem)
        throw new Error('Confirming the fix should load its problem first.')
      const source = problem
      const option =
        selected.external_id === '101'
          ? { tag_name: 'v4.13', name: '4.13' }
          : { tag_name: 'v4.14-rc1', name: '4.14 preview' }
      problem = {
        ...source,
        version: source.version + 1,
        fix_release: {
          provider: 'github',
          ...option,
          url: `https://github.com/acme/widgets/releases/tag/${option.tag_name}`,
          published_at: '2026-10-01T12:00:00Z',
          linked_by: { id: 'member-1', display_name: 'Test Member' },
          linked_at: '2026-10-02T12:00:00Z',
        },
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(problem),
      })
    },
  )
  await page.route(
    '**/api/workspaces/*/problems/*/fix-release/unlink/',
    async (route) => {
      if (!problem)
        throw new Error('Confirming the fix should load its problem first.')
      const source = problem
      problem = { ...source, version: source.version + 1, fix_release: null }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(problem),
      })
    },
  )

  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page)
  const marker = `Release link report ${Date.now()}`
  await page.getByRole('link', { name: 'New report' }).click()
  await page.getByLabel('Title').fill(marker)
  await page.getByLabel('Description').fill('The fix shipped in the release.')
  await page.getByLabel('Customer organisation').fill(`Customer ${marker}`)
  await page.getByRole('button', { name: 'Create report' }).click()
  await expect(page).toHaveURL(/\/inbox\/[0-9a-f-]{36}$/)
  await page.getByRole('button', { name: 'Create problem' }).click()
  await page.getByLabel('Problem title').fill('Release link acceptance flow')
  await page.getByRole('button', { name: 'Create and link' }).click()
  await page.getByRole('link', { name: 'Release link acceptance flow' }).click()
  await page.getByLabel('Fix details').fill('The fix shipped in the release.')
  await page.getByLabel('Available in version').fill('4.13')
  await page.getByRole('button', { name: 'Confirm fix' }).click()
  await expect(
    page.getByRole('region', { name: 'Confirmed fix' }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Link a release' }).click()
  const picker = page.getByRole('region', { name: 'Link a release' })
  await expect(picker.getByRole('radio', { name: /v4.13/ })).toBeVisible()
  expect(await axeViolations(page)).toEqual([])
  await picker.getByRole('radio', { name: /v4.13/ }).check()
  await picker.getByRole('button', { name: 'Link release' }).click()
  await expect(page.getByRole('link', { name: /v4.13/ })).toBeVisible()

  await page.getByRole('button', { name: 'Change release' }).click()
  const replacement = page.getByRole('region', { name: 'Link a release' })
  await replacement.getByRole('radio', { name: /v4.14-rc1/ }).check()
  await replacement.getByRole('button', { name: 'Link release' }).click()
  await expect(page.getByRole('link', { name: /v4.14-rc1/ })).toBeVisible()
  await page.getByRole('button', { name: 'Remove release' }).click()
  await expect(
    page.getByRole('button', { name: 'Link a release' }),
  ).toBeVisible()
})
