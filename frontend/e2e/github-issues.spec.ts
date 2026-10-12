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
  const title = `Synthetic GitHub issue flow ${Date.now()}`
  await page.goto('/inbox/new')
  await page.getByLabel('Title').fill(title)
  await page.getByLabel('Customer organisation').fill(`Customer ${title}`)
  await page.getByRole('button', { name: 'Create report' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
  await page.getByRole('button', { name: 'Create problem' }).click()
  await page.getByLabel('Problem title').fill(title)
  await page.getByRole('button', { name: 'Create and link' }).click()
  await expect(page.getByRole('link', { name: title })).toBeVisible()
  await page.getByRole('link', { name: title }).click()
  await expect(
    page.getByRole('heading', { name: 'GitHub issue', exact: true }),
  ).toBeVisible()
  return title
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
          body: body.body ?? 'Synthetic problem summary',
          marker,
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

test('renders a safe Markdown preview at phone width in both themes', async ({
  page,
}) => {
  const externalRequests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('images.example.com'))
      externalRequests.push(request.url())
  })
  await page.route('**/api/workspaces/*/problems/*/issue/preview/', (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        id: draftIds[0],
        draft_version: 1,
        expires_at: '2026-09-28T12:15:00Z',
        title: 'Markdown preview issue',
        body:
          '# Preview\n\n- [x] Ready\n\n| Field | Value |\n| --- | --- |\n| Example | Content |\n\n```text\n' +
          'x'.repeat(400) +
          '\n```\n\n[Docs](https://example.com/docs) ![Chart](https://images.example.com/chart.png)\n\n<script>alert(1)</script>',
        marker: `<!-- rescribo-operation:${draftIds[0]} -->`,
        repository: 'acme/widgets',
        visibility: 'private',
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
  await issueSection.getByRole('button', { name: 'Preview issue' }).click()
  const preview = issueSection.getByText('Exact preview').locator('..')
  await expect(
    preview.getByRole('heading', { name: 'Preview', level: 5 }),
  ).toBeVisible()
  const link = preview.getByRole('link', { name: 'Docs' })
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  await expect(preview).toContainText('<script>alert(1)</script>')
  await expect(preview.locator('script, img')).toHaveCount(0)
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true)
  expect(externalRequests).toEqual([])
  expect(await axeViolations(page)).toEqual([])
  await page
    .locator('html')
    .evaluate((element) => element.setAttribute('data-theme', 'dark'))
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await axeViolations(page)).toEqual([])
})
