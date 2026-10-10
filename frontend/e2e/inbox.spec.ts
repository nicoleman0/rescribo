import { AxeBuilder } from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  expectTouchTarget,
  expectVisibleControlTouchTargets,
} from './touch-target.js'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = { users: { email: string; password: string }[] }

// Axe needs settled colours rather than a frame from the content fade.
test.use({ reducedMotion: 'reduce' })

// The seed command creates this synthetic Slack report in the e2e workspace.
const seededTitle = 'Synthetic Slack report'

async function signIn(page: Page) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto('/sign-in')
  // Other specs change the member's password, so use an owner whose
  // credentials stay fixed.
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[2].email)
  await page.getByLabel('Password').fill(seed.users[2].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await expect(page).toHaveTitle('Inbox · Rescribo')
}

const reportList = (page: Page) => page.getByRole('list', { name: 'Reports' })

const statusChip = (page: Page, label: string) =>
  page
    .getByRole('group', { name: 'Status' })
    .getByRole('button', { name: new RegExp(`^${label}\\b`) })

// The router commits URL changes in a transition. Wait for each filter change
// to land before the next one, or the next handler can reuse stale filters.
const expectSearch = (page: Page, search: string) =>
  expect.poll(() => new URL(page.url()).search).toBe(search)

// The URL clears before the filter bar re-renders, so also wait for the button
// to go; input before that lands in the old bar and is lost.
async function clearFilters(page: Page) {
  const clear = page.getByRole('button', { name: 'Clear filters' })
  await clear.click()
  await expectSearch(page, '')
  await expect(clear).toHaveCount(0)
}

test.describe('Inbox', () => {
  test.beforeEach(async ({ page }) => signIn(page))

  test('captures a manual report, then searches and filters the inbox', async ({
    page,
  }) => {
    const marker = `Manual e2e ${Date.now()}`
    await page.getByRole('link', { name: 'New report' }).click()
    await expect(page).toHaveURL(/\/inbox\/new$/)
    await expect(page).toHaveTitle('New report · Rescribo')
    await page.getByLabel('Title').fill(marker)
    await page.getByLabel('Description').fill('Export stops at 50%.')
    await page.getByLabel('Customer organisation').fill(`Customer ${marker}`)
    await page.getByLabel('Affected version').fill('2.3.1')
    await page.getByRole('button', { name: 'Create report' }).click()

    await expect(page).toHaveURL(/\/inbox\/[0-9a-f-]{36}$/)
    const detail = page.getByRole('region', { name: 'Report detail' })
    await expect(detail.getByRole('heading', { name: marker })).toBeVisible()
    await expect(detail).toContainText('2.3.1')
    await expect(detail).toContainText('Unassigned')
    await expect(detail).toContainText('Not linked')
    await expect(
      detail.getByRole('region', { name: 'Provenance' }),
    ).toContainText('Manual entry by')
    await detail.getByRole('link', { name: 'Back to reports' }).click()
    await expect(page).toHaveURL(/\/inbox$/)

    await page.getByRole('searchbox', { name: 'Search reports' }).fill(marker)
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/q=Manual/)
    await expect(reportList(page).getByRole('listitem')).toHaveCount(1)
    await expect(reportList(page)).toContainText(marker)

    await clearFilters(page)
    await page
      .getByRole('searchbox', { name: 'Customer' })
      .fill('seeded customer')
    await page.getByRole('button', { name: 'Search' }).click()
    await expectSearch(page, '?customer=seeded+customer')
    await expect(reportList(page).getByRole('listitem')).toHaveCount(1)
    await expect(reportList(page)).toContainText(seededTitle)

    await clearFilters(page)
    await page.getByLabel('Source').selectOption('slack')
    await expectSearch(page, '?source_kind=slack')
    await expect(reportList(page)).toContainText(seededTitle)
    await expect(reportList(page)).not.toContainText(marker)
    await page.getByLabel('Source').selectOption('manual')
    await expectSearch(page, '?source_kind=manual')
    await expect(reportList(page)).toContainText(marker)
    await expect(reportList(page)).not.toContainText(seededTitle)

    await page.getByLabel('Source').selectOption('')
    await expectSearch(page, '')
    await page
      .getByRole('region', { name: 'Search and filter reports' })
      .getByLabel('Assignee')
      .selectOption('unassigned')
    await expectSearch(page, '?assignee=unassigned')
    await statusChip(page, 'New').click()
    await expectSearch(page, '?assignee=unassigned&triage_state=new')
    await expect(reportList(page)).toContainText(marker)
    await expect(statusChip(page, 'New')).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await statusChip(page, 'Dismissed').click()
    await expect(page.getByText('No reports match these filters')).toBeVisible()

    await page.getByRole('button', { name: 'Clear filters' }).first().click()
    await expectSearch(page, '')
    await reportList(page).getByRole('link', { name: seededTitle }).click()
    const provenance = page
      .getByRole('region', { name: 'Report detail' })
      .getByRole('region', { name: 'Provenance' })
    await expect(provenance).toContainText('Slack message by Synthetic Author')
    await expect(provenance).toContainText('Synthetic captured message.')
    await expect(provenance).toContainText(
      'The message link is not available yet.',
    )
  })

  test('keeps an unsaved draft when creation fails', async ({ page }) => {
    await page.route('**/api/workspaces/*/reports/', (route) =>
      route.request().method() === 'POST' ? route.abort() : route.continue(),
    )
    await page.goto('/inbox/new')
    await page.getByLabel('Title').fill('Draft that must survive')
    await page.getByLabel('Contact reference').fill('CRM-42')
    await page.getByRole('button', { name: 'Create report' }).click()
    await expect(
      page.getByText('Could not confirm report creation'),
    ).toBeVisible()
    await expect(page.getByText(/Could not reach Rescribo/)).toBeVisible()
    await expect(page.getByLabel('Title')).toHaveValue(
      'Draft that must survive',
    )

    await page.unroute('**/api/workspaces/*/reports/')
    await page.reload()
    await expect(page.getByText('Restored your unsaved draft')).toBeVisible()
    await expect(page.getByLabel('Title')).toHaveValue(
      'Draft that must survive',
    )
    await expect(page.getByLabel('Contact reference')).toHaveValue('CRM-42')
    await page.getByRole('button', { name: 'Discard draft' }).click()
    await expect(page.getByLabel('Title')).toHaveValue('')
    await page.reload()
    await expect(page.getByText('Restored your unsaved draft')).toHaveCount(0)
  })

  test('retries a committed report after its response is lost and the page reloads', async ({
    page,
  }) => {
    const marker = `Lost response ${randomUUID()}`
    let committedId = ''
    let submissionKey = ''
    let reportsUrl = ''
    let workspaceId = ''
    await page.route('**/api/workspaces/*/reports/', async (route) => {
      const request = route.request()
      if (
        request.method() !== 'POST' ||
        request.postDataJSON().title !== marker
      ) {
        await route.continue()
        return
      }
      submissionKey = request.postDataJSON().submission_key
      reportsUrl = request.url()
      workspaceId = new URL(reportsUrl).pathname.split('/')[3]
      const response = await route.fetch({ maxRetries: 0 })
      expect(response.status()).toBe(201)
      committedId = (await response.json()).id
      expect(committedId).toMatch(/^[0-9a-f-]{36}$/)
      await route.abort('failed')
    })
    await page.goto('/inbox/new')
    await page.getByLabel('Title').fill(marker)
    await page
      .getByLabel('Description')
      .fill('Synthetic committed request, lost response.')
    await page.getByRole('button', { name: 'Create report' }).click()
    await expect(
      page.getByText('Could not confirm report creation'),
    ).toBeVisible()
    await expect(page.getByLabel('Title')).toHaveValue(marker)
    await page.unroute('**/api/workspaces/*/reports/')
    await page.reload()
    await expect(page.getByText('Restored your unsaved draft')).toBeVisible()
    await expect(page.getByLabel('Title')).toHaveValue(marker)
    const restoredKey = await page.evaluate(
      (id) =>
        JSON.parse(sessionStorage.getItem(`rescribo:report-draft:${id}`)!)
          .submission_key,
      workspaceId,
    )
    expect(restoredKey).toBe(submissionKey)
    const retryResponse = page.waitForResponse(
      (response) =>
        response.url() === reportsUrl && response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: 'Create report' }).click()
    const replay = await retryResponse
    expect(replay.request().postDataJSON().submission_key).toBe(submissionKey)
    expect(replay.status()).toBe(200)
    expect((await replay.json()).id).toBe(committedId)
    await expect(page).toHaveURL(new RegExp(`/inbox/${committedId}$`))
    await expect(
      page.getByRole('region', { name: 'Report detail' }),
    ).toContainText(marker)
    expect(
      await page.evaluate(
        (id) => sessionStorage.getItem(`rescribo:report-draft:${id}`),
        workspaceId,
      ),
    ).toBeNull()
    await page.getByRole('link', { name: 'Back to reports' }).click()
    await page.getByRole('searchbox', { name: 'Search reports' }).fill(marker)
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(reportList(page).getByRole('listitem')).toHaveCount(1)
    await expect(reportList(page)).toContainText(marker)
    const listing = await page.request.get(
      `${reportsUrl}?q=${encodeURIComponent(marker)}`,
    )
    expect(listing.status()).toBe(200)
    const body = await listing.json()
    expect(body.count).toBe(1)
    expect(body.results[0].id).toBe(committedId)
  })

  test('shows an error with retry when the inbox cannot load', async ({
    page,
  }) => {
    let available = false
    await page.route('**/api/workspaces/*/reports/**', (route) =>
      available
        ? route.continue()
        : route.fulfill({ status: 503, json: { detail: 'Unavailable' } }),
    )
    await page.goto('/inbox?customer=seeded')
    // The app's query client retries with backoff before showing the error.
    await expect(page.getByText('Could not load reports')).toBeVisible({
      timeout: 20_000,
    })
    available = true
    await page.getByRole('button', { name: 'Try again' }).click()
    await expect(reportList(page)).toContainText(seededTitle)
  })

  test('is keyboard operable and has no axe violations', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await page.goto('/inbox')
    await expect(reportList(page)).toContainText(seededTitle)
    const search = page.getByRole('searchbox', { name: 'Search reports' })
    await search.focus()
    await page.keyboard.type('synthetic')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/q=synthetic/)
    const report = reportList(page).getByRole('link', { name: seededTitle })
    await report.focus()
    await page.keyboard.press('Enter')
    await expect(
      page.getByRole('region', { name: 'Report detail' }),
    ).toContainText('Synthetic captured message.')
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await page.goto('/inbox/new')
    await expect(page.getByLabel('Title')).toBeVisible()
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  })

  test('stacks the list and detail at mobile width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/inbox')
    const filters = page.getByRole('button', { name: 'Filters' })
    await expect(
      page.getByRole('searchbox', { name: 'Search reports' }),
    ).toBeInViewport()
    await expect(filters).toBeInViewport()
    await expect(reportList(page).getByRole('link').first()).toBeInViewport()
    await expect(page.getByRole('group', { name: 'Status' })).toBeHidden()
    await filters.click()
    await expect(filters).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByRole('group', { name: 'Status' })).toBeVisible()

    await page.goto('/inbox?customer=seeded')
    await expect(
      page.getByRole('button', { name: /^Filters\W+1 active$/ }),
    ).toBeVisible()
    await reportList(page).getByRole('link', { name: seededTitle }).click()
    const detail = page.getByRole('region', { name: 'Report detail' })
    await expect(detail).toBeVisible()
    await expect(reportList(page)).toBeHidden()
    const hasOverflow = await page.evaluate<boolean>(
      'document.documentElement.scrollWidth > window.innerWidth',
    )
    expect(hasOverflow).toBe(false)
    await detail.getByRole('link', { name: 'Back to reports' }).click()
    await expect(page).toHaveURL(/\/inbox\?customer=seeded$/)
    await expect(reportList(page)).toBeVisible()
  })

  test('phone controls meet the touch target minimum', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/inbox')
    await expectVisibleControlTouchTargets(page)
    await expectTouchTarget(page.getByRole('link', { name: 'New report' }))
    await expectTouchTarget(reportList(page).getByRole('link').first())

    await page.getByRole('button', { name: 'Filters' }).click()
    await expectVisibleControlTouchTargets(page)
    await page.getByLabel('Source').selectOption('manual')
    await expectVisibleControlTouchTargets(page)
    await page
      .getByRole('region', { name: 'Search and filter reports' })
      .getByRole('button', { name: 'Clear filters' })
      .click()
    await expectSearch(page, '')

    await page.goto('/inbox/new')
    await expectVisibleControlTouchTargets(page)

    await page.route('**/api/workspaces/*/reports/**', async (route) => {
      const requestUrl = new URL(route.request().url())
      if (requestUrl.searchParams.get('page') === '2') {
        await route.fulfill({ status: 404, json: { detail: 'Not found' } })
        return
      }
      const response = await route.fetch()
      const body = (await response.json()) as Record<string, unknown>
      body.next = `${requestUrl.origin}${requestUrl.pathname}?page=2`
      await route.fulfill({ response, json: body })
    })
    await page.goto('/inbox')
    await expectVisibleControlTouchTargets(page)
    const pageTwoResponse = page.waitForResponse(
      (response) => new URL(response.url()).searchParams.get('page') === '2',
    )
    await page.getByRole('button', { name: 'Next' }).click()
    expect((await pageTwoResponse).status()).toBe(404)
    await expect(page.getByText('This page has no reports')).toBeVisible({
      timeout: 20_000,
    })
    await expectVisibleControlTouchTargets(page)
    await expectTouchTarget(
      page.getByRole('button', { name: 'Go to the first page' }),
    )
  })
})
