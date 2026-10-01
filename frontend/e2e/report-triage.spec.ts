import { expect, test, type Browser, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const seedPath = path.join(authDir, 'seed.json')
const sessionPath = path.join(authDir, 'triage-owner.json')
type Seed = { users: { email: string; password: string }[] }

// The seed command creates this Slack report for this spec alone, so other
// specs keep their shared report untouched.
const slackTitle = 'Synthetic Slack triage report'

// Sign in once and reuse the session: login is throttled per identity and
// address. No other spec signs in as this owner or changes its password.
async function saveSession(browser: Browser, baseURL?: string) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  // Start signed out; test.use would otherwise load the file being created.
  const page = await browser.newPage({
    baseURL,
    storageState: { cookies: [], origins: [] },
  })
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[4].email)
  await page.getByLabel('Password').fill(seed.users[4].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.context().storageState({ path: sessionPath })
  await page.close()
}

const detail = (page: Page) =>
  page.getByRole('region', { name: 'Report detail' })
const triage = (page: Page) =>
  detail(page).getByRole('region', { name: 'Triage' })
const linkedReports = (page: Page) =>
  page.getByRole('list', { name: 'Linked reports' })
const activity = (page: Page) =>
  page.getByRole('list', { name: 'Problem activity' })

async function createManualReport(page: Page, title: string) {
  await page.goto('/inbox/new')
  await page.getByLabel('Title').fill(title)
  await page.getByLabel('Customer organisation').fill(`Customer ${title}`)
  await page.getByRole('button', { name: 'Create report' }).click()
  await expect(detail(page).getByRole('heading', { name: title })).toBeVisible()
  return page.url()
}

async function openReport(page: Page, title: string) {
  await page.goto(`/inbox?q=${encodeURIComponent(title)}`)
  await page
    .getByRole('list', { name: 'Reports' })
    .getByRole('link', { name: new RegExp(title) })
    .click()
  await expect(detail(page).getByRole('heading', { name: title })).toBeVisible()
}

async function createProblem(page: Page, title: string, move = false) {
  await triage(page)
    .getByRole('button', {
      name: move ? 'Move to new problem' : 'Create problem',
    })
    .click()
  await page.getByLabel('Problem title').fill(title)
  await page
    .getByRole('button', { name: move ? 'Create and move' : 'Create and link' })
    .click()
  await expect(
    triage(page).getByRole('button', { name: 'Ungroup' }),
  ).toBeVisible()
  await expect(detail(page).getByRole('link', { name: title })).toBeVisible()
}

async function pickProblem(page: Page, title: string) {
  await page.getByRole('searchbox', { name: 'Find a problem' }).fill(title)
  await page.getByRole('searchbox', { name: 'Find a problem' }).press('Enter')
  await page.getByRole('radio', { name: new RegExp(title) }).check()
}

async function openProblem(page: Page, title: string) {
  await detail(page).getByRole('link', { name: title }).click()
  await expect(
    page.getByRole('heading', { level: 1, name: title }),
  ).toBeVisible()
}

test.describe('Report triage', () => {
  test.beforeAll(async ({ browser }, info) =>
    saveSession(browser, info.project.use.baseURL),
  )
  test.use({ storageState: sessionPath })

  test('confirms fixes after moving a report and verifies applicability for a late report', async ({
    page,
  }) => {
    const marker = `Fix ${Date.now()}`
    const reportTitle = `Report ${marker}`
    const firstProblem = `First ${marker}`
    const secondProblem = `Second ${marker}`
    await createManualReport(page, reportTitle)
    await createProblem(page, firstProblem)
    await openProblem(page, firstProblem)
    await page.getByLabel('Fix details').fill('First fix is available')
    await page.getByLabel('Available in version').fill('1.0')
    await page.getByRole('button', { name: 'Confirm fix', exact: true }).click()
    await expect(
      page.getByRole('region', { name: 'Confirmed fix' }),
    ).toContainText('First fix is available')

    await openReport(page, reportTitle)
    await createProblem(page, secondProblem, true)
    await openProblem(page, secondProblem)
    await page.getByLabel('Fix details').fill('Second fix is available')
    await page.getByLabel('Available in version').fill('2.0')
    await page.getByRole('button', { name: 'Confirm fix', exact: true }).click()
    await expect(
      page.getByRole('region', { name: 'Confirmed fix' }),
    ).toContainText('Second fix is available')
    await expect(
      page.getByRole('button', { name: 'Confirm fix applies' }),
    ).toHaveCount(0)

    await createManualReport(page, `Late ${marker}`)
    await triage(page).getByRole('button', { name: 'Link to problem' }).click()
    await pickProblem(page, secondProblem)
    await page.getByRole('button', { name: 'Link report' }).click()
    await expect(
      triage(page).getByRole('button', { name: 'Ungroup' }),
    ).toBeVisible()
    await openProblem(page, secondProblem)
    const confirm = page.getByRole('button', { name: 'Confirm fix applies' })
    await expect(confirm).toHaveCount(1)
    await confirm.click()
    await expect(confirm).toHaveCount(0)
    await page.reload()
    await expect(linkedReports(page).getByRole('listitem')).toHaveCount(2)
    await expect(confirm).toHaveCount(0)
  })

  test('groups two reports into one problem, then moves, reassigns, ungroups, dismisses, and restores', async ({
    page,
  }) => {
    const marker = `Triage ${Date.now()}`
    const manualTitle = `Manual ${marker}`
    const problemA = `Problem A ${marker}`
    const problemB = `Problem B ${marker}`
    await createManualReport(page, manualTitle)

    // First report: the seeded Slack capture creates a new problem.
    await openReport(page, slackTitle)
    await createProblem(page, problemA)

    // Second report: link the manual report through the existing-problem picker.
    await openReport(page, manualTitle)
    await triage(page).getByRole('button', { name: 'Link to problem' }).click()
    await pickProblem(page, problemA)
    await page.getByRole('button', { name: 'Link report' }).click()
    await expect(
      triage(page).getByRole('button', { name: 'Ungroup' }),
    ).toBeVisible()
    await openProblem(page, problemA)

    await expect(page.getByText('2 reports · v1')).toBeVisible()
    await expect(page.getByText('Open', { exact: true })).toBeVisible()
    await expect(page.getByLabel('Owner')).toHaveValue('')
    const reports = linkedReports(page)
    await expect(reports.getByRole('listitem')).toHaveCount(2)
    const slackItem = reports
      .getByRole('listitem')
      .filter({ hasText: slackTitle })
    const manualItem = reports
      .getByRole('listitem')
      .filter({ hasText: manualTitle })
    await expect(slackItem).toContainText('Slack message by Synthetic Author')
    await expect(slackItem).toContainText('Synthetic captured message.')
    await expect(manualItem).toContainText('Manual entry by Owner')
    await expect(activity(page)).toContainText(`linked ${slackTitle}`)
    await expect(activity(page)).toContainText(`linked ${manualTitle}`)

    // Assign, then reassign, from problem detail; both survive a reload.
    const assignee = manualItem.getByLabel('Assignee')
    await assignee.selectOption({ label: 'Member' })
    await manualItem.getByRole('button', { name: 'Save assignee' }).click()
    await expect(
      manualItem.getByRole('button', { name: 'Save assignee' }),
    ).toBeDisabled()
    await expect(activity(page)).toContainText(
      `assigned ${manualTitle} to Member`,
    )
    // The member list order is not defined, so reassign by label, not index.
    await assignee.selectOption({ label: 'Owner' })
    await manualItem.getByRole('button', { name: 'Save assignee' }).click()
    await expect(activity(page)).toContainText(
      `assigned ${manualTitle} to Owner`,
    )
    const reassignedTo = await assignee.inputValue()
    await page.reload()
    await expect(linkedReports(page).getByRole('listitem')).toHaveCount(2)
    await expect(
      linkedReports(page)
        .getByRole('listitem')
        .filter({ hasText: manualTitle })
        .getByLabel('Assignee'),
    ).toHaveValue(reassignedTo)
    await expect(
      linkedReports(page)
        .getByRole('listitem')
        .filter({ hasText: manualTitle }),
    ).toContainText('Submitted by Owner')
    await expect(
      linkedReports(page).getByRole('listitem').filter({ hasText: slackTitle }),
    ).toContainText('Synthetic captured message.')

    // Move the manual report to a new problem; both counts and histories change.
    await openReport(page, manualTitle)
    await createProblem(page, problemB, true)
    await page.goto(`/problems?q=${encodeURIComponent(marker)}`)
    const problems = page.getByRole('list', { name: 'Problems' })
    await expect(
      problems.getByRole('link', { name: new RegExp(problemA) }),
    ).toContainText('1 report')
    await expect(
      problems.getByRole('link', { name: new RegExp(problemB) }),
    ).toContainText('1 report')
    await problems.getByRole('link', { name: new RegExp(problemB) }).click()
    await expect(activity(page)).toContainText(
      `moved ${manualTitle} here from ${problemA}`,
    )

    // Ungroup, dismiss, and restore; provenance is unchanged throughout.
    await openReport(page, manualTitle)
    await triage(page).getByRole('button', { name: 'Ungroup' }).click()
    await expect(detail(page)).toContainText('Not linked')
    await expect(detail(page).getByText('New', { exact: true })).toBeVisible()
    await triage(page).getByRole('button', { name: 'Dismiss' }).click()
    await expect(
      detail(page).getByText('Dismissed', { exact: true }),
    ).toBeVisible()
    await triage(page).getByRole('button', { name: 'Restore report' }).click()
    await expect(detail(page).getByText('New', { exact: true })).toBeVisible()
    await page.reload()
    await expect(
      detail(page).getByRole('region', { name: 'Provenance' }),
    ).toContainText('Manual entry by Owner')
    await expect(detail(page)).toContainText(`Customer ${manualTitle}`)

    // The first problem keeps the history of the report that left it.
    await page.goto(`/problems?q=${encodeURIComponent(problemA)}`)
    await page.getByRole('link', { name: new RegExp(problemA) }).click()
    await expect(linkedReports(page).getByRole('listitem')).toHaveCount(1)
    await expect(activity(page)).toContainText(
      `moved ${manualTitle} to ${problemB}`,
    )
    await page.goto(`/problems?q=${encodeURIComponent(problemB)}`)
    await page.getByRole('link', { name: new RegExp(problemB) }).click()
    await expect(page.getByText('No reports are linked.')).toBeVisible()
    await expect(activity(page)).toContainText(`ungrouped ${manualTitle}`)
  })

  test('keeps a stale problem edit and retries against the current version', async ({
    page,
    context,
  }) => {
    const title = `Stale ${Date.now()}`
    await createManualReport(page, title)
    await createProblem(page, title)
    await openProblem(page, title)
    await page.getByRole('button', { name: 'Edit title and summary' }).click()
    await page.getByLabel('Summary').fill('My summary')

    const other = await context.newPage()
    await other.goto(page.url())
    await other.getByRole('button', { name: 'Edit title and summary' }).click()
    await other.getByLabel('Title').fill(`${title} renamed`)
    await other.getByRole('button', { name: 'Save changes' }).click()
    await expect(
      other.getByRole('heading', { level: 1, name: `${title} renamed` }),
    ).toBeVisible()
    await other.close()

    await page.getByRole('button', { name: 'Save changes' }).click()
    await expect(page.getByText('The problem was not saved')).toBeVisible()
    await expect(page.getByText(/changed while you were working/)).toBeVisible()
    await expect(page.getByLabel('Summary')).toHaveValue('My summary')
    await page.getByRole('button', { name: 'Save changes' }).click()
    // The form closes only after the retry is saved.
    await expect(
      page.getByRole('button', { name: 'Edit title and summary' }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', { level: 1, name: `${title} renamed` }),
    ).toBeVisible()
    await expect(page.getByText('My summary')).toBeVisible()
    await page.reload()
    await expect(page.getByText('My summary')).toBeVisible()
  })

  test('keeps the chosen problem when linking fails, then links on retry', async ({
    page,
  }) => {
    const title = `Retry ${Date.now()}`
    await createManualReport(page, `${title} first`)
    await createProblem(page, title)
    await createManualReport(page, `${title} second`)
    await triage(page).getByRole('button', { name: 'Link to problem' }).click()
    await pickProblem(page, title)
    await page.route('**/api/workspaces/*/reports/*/link/', (route) =>
      route.abort(),
    )
    await page.getByRole('button', { name: 'Link report' }).click()
    await expect(page.getByText('The report was not linked')).toBeVisible()
    await expect(page.getByText(/Could not reach Rescribo/)).toBeVisible()
    await expect(
      page.getByRole('radio', { name: new RegExp(title) }),
    ).toBeChecked()
    await expect(detail(page)).toContainText('Not linked')
    await page.unroute('**/api/workspaces/*/reports/*/link/')
    await page.getByRole('button', { name: 'Link report' }).click()
    await expect(detail(page).getByRole('link', { name: title })).toBeVisible()
  })

  test('is keyboard operable, accessible, and fits a phone', async ({
    page,
  }) => {
    const title = `Keyboard ${Date.now()}`
    await page.setViewportSize({ width: 1280, height: 900 })
    await createManualReport(page, title)
    const create = triage(page).getByRole('button', { name: 'Create problem' })
    await create.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByLabel('Problem title')).toHaveValue(title)
    expect(await axeViolations(page)).toEqual([])
    await page.getByRole('button', { name: 'Cancel' }).focus()
    await page.keyboard.press('Enter')
    await expect(create).toBeFocused()

    await page.keyboard.press('Enter')
    await page.getByLabel('Problem title').focus()
    await page.keyboard.press('Enter')
    await expect(
      triage(page).getByRole('heading', { name: 'Triage' }),
    ).toBeFocused()
    await expect(
      triage(page).getByRole('button', { name: 'Ungroup' }),
    ).toBeVisible()
    await triage(page).getByRole('button', { name: 'Move to problem' }).click()
    await expect(
      page.getByRole('status', { name: 'Loading problems' }),
    ).toHaveCount(0)
    expect(await axeViolations(page)).toEqual([])
    await page.getByRole('button', { name: 'Cancel' }).click()

    await openProblem(page, title)
    await expect(activity(page)).toContainText('created the problem')
    expect(await axeViolations(page)).toEqual([])
    await page.goto('/problems')
    await expect(page.getByRole('list', { name: 'Problems' })).toBeVisible()
    expect(await axeViolations(page)).toEqual([])
    const search = page.getByRole('searchbox', { name: 'Search problems' })
    await search.focus()
    await page.keyboard.type(title)
    await page.keyboard.press('Enter')
    const result = page.getByRole('link', { name: new RegExp(title) })
    await result.focus()
    await page.keyboard.press('Enter')
    await expect(
      page.getByRole('heading', { level: 1, name: title }),
    ).toBeVisible()

    await page.setViewportSize({ width: 375, height: 812 })
    await page.reload()
    await expect(linkedReports(page)).toBeVisible()
    const overflow = () =>
      page.evaluate<boolean>(
        'document.documentElement.scrollWidth > window.innerWidth',
      )
    expect(await overflow()).toBe(false)
    for (const name of [
      'Edit title and summary',
      'Save owner',
      'Save assignee',
    ]) {
      const box = await page.getByRole('button', { name }).first().boundingBox()
      expect(box?.height).toBeGreaterThanOrEqual(44)
    }
    await page.getByRole('link', { name: title }).last().click()
    await expect(triage(page)).toBeVisible()
    expect(await overflow()).toBe(false)
    for (const name of ['Move to problem', 'Move to new problem', 'Ungroup']) {
      const box = await triage(page).getByRole('button', { name }).boundingBox()
      expect(box?.height).toBeGreaterThanOrEqual(44)
    }
  })
})
