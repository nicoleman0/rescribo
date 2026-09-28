import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = { users: { email: string; password: string }[] }
const operationId = '33333333-3333-4333-8333-333333333333'
const draftIds = [
  '11111111-1111-4111-8111-111111111111',
  '22222222-2222-4222-8222-222222222222',
]

async function signIn(page: Page) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[2].email)
  await page.getByLabel('Password').fill(seed.users[2].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
}

async function createProblem(page: Page) {
  await page.getByRole('link', { name: 'Synthetic Slack report' }).click()
  await page.getByRole('button', { name: 'Create problem' }).click()
  await page.getByLabel('Problem title').fill('Synthetic GitHub issue flow')
  await page.getByRole('button', { name: 'Create and link' }).click()
  await expect(
    page.getByRole('link', { name: 'Synthetic GitHub issue flow' }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Synthetic GitHub issue flow' }).click()
  await expect(
    page.getByRole('heading', { name: 'GitHub issue', exact: true }),
  ).toBeVisible()
}

test('links to a responsive preview and publishes only after keyboard approval', async ({
  page,
}) => {
  let previewCount = 0
  let approved: Record<string, unknown> | undefined
  await page.route(
    '**/api/workspaces/*/problems/*/issue/preview/',
    async (route) => {
      previewCount += 1
      const body = route.request().postDataJSON() as {
        title?: string
        body?: string
      }
      const marker = `<!-- rescribo-operation:${draftIds[previewCount - 1]} -->`
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: draftIds[previewCount - 1],
          draft_version: 1,
          expires_at: '2026-09-28T12:15:00Z',
          title: body.title ?? 'Synthetic GitHub issue flow',
          body: `${body.body ?? 'Synthetic problem summary'}\n\n${marker}`,
          repository: 'acme/widgets',
          visibility: 'private',
        }),
      })
    },
  )
  await page.route(
    '**/api/workspaces/*/problems/*/issue/approve/',
    async (route) => {
      approved = route.request().postDataJSON() as Record<string, unknown>
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          id: operationId,
          state: 'queued',
          destination: 'acme/widgets',
          remote_issue_id: '',
          remote_number: null,
          remote_url: '',
          safe_error: '',
          created_at: '2026-09-28T12:00:00Z',
          approved_at: '2026-09-28T12:00:01Z',
          completed_at: null,
        }),
      })
    },
  )
  await page.route(
    `**/api/workspaces/*/problems/*/issue/operations/${operationId}/`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: operationId,
          state: 'queued',
          destination: 'acme/widgets',
          remote_issue_id: '',
          remote_number: null,
          remote_url: '',
          safe_error: '',
          created_at: '2026-09-28T12:00:00Z',
          approved_at: '2026-09-28T12:00:01Z',
          completed_at: null,
        }),
      }),
  )

  await page.setViewportSize({ width: 390, height: 844 })
  await signIn(page)
  await createProblem(page)
  const issueSection = page.getByRole('region', { name: 'GitHub issue' })
  await issueSection
    .getByRole('button', { name: 'Create GitHub issue' })
    .click()
  const title = page.getByRole('textbox', { name: 'Issue title' })
  await title.fill('Reviewed issue from problem')
  await page
    .getByRole('textbox', { name: 'Issue body' })
    .fill('Reviewed body without report details')
  await title.press('Enter')
  await expect(issueSection.getByText('Exact preview')).toBeVisible()
  await expect(issueSection).toContainText(
    'Reviewed body without report details',
  )
  await expect(issueSection).toContainText(`rescribo-operation:${draftIds[1]}`)
  await expect(
    issueSection.getByRole('button', { name: 'Publish issue' }),
  ).toBeVisible()
  await page.setViewportSize({ width: 1280, height: 900 })
  await issueSection
    .getByRole('button', { name: 'Publish issue' })
    .press('Enter')
  await expect(page.getByText('Issue creation is queued.')).toBeVisible()
  expect(previewCount).toBe(2)
  expect(approved).toEqual({
    draft_id: draftIds[1],
    draft_version: 1,
    approved: true,
  })
})
