import { expect, test, type Page } from '@playwright/test'
import { axeViolations } from './axe.js'
import { saveSeedSession, seedSessionPath } from './seed-session.js'
import { expectTouchTarget } from './touch-target.js'

// The seed command creates this Slack report for this spec alone, so other
// specs keep their shared report untouched.
const slackTitle = 'Synthetic Slack triage report'

// Sign in once and reuse the session: login is throttled per identity and
// address, and no other spec saves a session for this user.

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
    saveSeedSession(
      browser,
      info.project.use.baseURL,
      seedSessionPath('triage-owner'),
      4,
    ),
  )
  test.use({ storageState: seedSessionPath('triage-owner') })

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
    // The button reads "Recording…" while the CSRF and confirm requests run,
    // so its count drops before the confirmation is saved.
    const confirmed = page.waitForResponse(
      (response) =>
        response.url().includes('/confirm-fix-applies/') &&
        response.request().method() === 'POST',
    )
    await confirm.click()
    expect((await confirmed).ok()).toBe(true)
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
    await expect(page.getByText('No owner')).toBeVisible()
    const reports = linkedReports(page)
    await expect(reports.getByRole('listitem')).toHaveCount(2)
    const slackItem = reports
      .getByRole('listitem')
      .filter({ hasText: slackTitle })
    const manualItem = reports
      .getByRole('listitem')
      .filter({ hasText: manualTitle })
    await expect(slackItem).toContainText('Slack message by Synthetic Author')
    await expect(manualItem).toContainText('Manual entry by Owner')
    // Both links may fold into one "linked 2 reports" entry.
    await expect(activity(page)).toContainText('linked')
    await expect(activity(page)).toContainText(slackTitle)
    await expect(activity(page)).toContainText(manualTitle)

    // Assign, then reassign, from problem detail by choosing; both survive a
    // reload. The first toast is checked with reduced motion on.
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const assigneeTrigger = manualItem.getByRole('combobox', {
      name: new RegExp(`^Assignee for ${manualTitle}`),
    })
    await assigneeTrigger.click()
    await expect(
      page.getByText(/cancels any unsent employee notification/).first(),
    ).toBeVisible()
    await page
      .getByRole('option', { name: 'Member', exact: true })
      .first()
      .click()
    await expect(assigneeTrigger).toHaveAccessibleName(/: Member$/)
    const toast = page.locator('[data-sonner-toast]').first()
    await expect(toast).toContainText('Assigned to Member')
    expect(
      await toast.evaluate((element) => ({
        running: element.getAnimations().length,
        transition: getComputedStyle(element).transitionDuration,
      })),
    ).toEqual({ running: 0, transition: '0s' })
    await expect(activity(page)).toContainText(
      `assigned ${manualTitle} to Member`,
    )
    // The member list order is not defined, so choose by name, not index.
    await assigneeTrigger.click()
    await page
      .getByRole('option', { name: 'Owner', exact: true })
      .first()
      .click()
    await expect(activity(page)).toContainText(
      `assigned ${manualTitle} to Owner`,
    )
    await page.reload()
    await expect(linkedReports(page).getByRole('listitem')).toHaveCount(2)
    await expect(
      linkedReports(page)
        .getByRole('listitem')
        .filter({ hasText: manualTitle }),
    ).toContainText('Owner')
    await expect(
      linkedReports(page).getByRole('listitem').filter({ hasText: slackTitle }),
    ).toContainText('Slack message by Synthetic Author')

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
    await triage(page)
      .getByRole('button', { name: 'Ungroup', exact: true })
      .click()
    await triage(page).getByRole('button', { name: 'Ungroup report' }).click()
    await expect(detail(page)).toContainText('Not linked')
    await expect(detail(page).getByText('New', { exact: true })).toBeVisible()
    await triage(page)
      .getByRole('button', { name: 'Dismiss', exact: true })
      .dblclick()
    await expect(
      triage(page).getByRole('form', { name: 'Dismiss this report?' }),
    ).toBeVisible()
    await expect(detail(page).getByText('New', { exact: true })).toBeVisible()
    await triage(page).getByRole('button', { name: 'Dismiss report' }).click()
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
    const ungroup = triage(page).getByRole('button', {
      name: 'Ungroup',
      exact: true,
    })
    await ungroup.focus()
    await page.keyboard.press('Enter')
    const ungroupForm = triage(page).getByRole('form', {
      name: 'Ungroup this report?',
    })
    await expect(
      ungroupForm.getByRole('heading', { name: 'Ungroup this report?' }),
    ).toBeFocused()
    expect(await axeViolations(page)).toEqual([])
    await page.keyboard.press('Enter')
    await expect(ungroupForm).toBeVisible()
    await page.keyboard.press('Tab')
    await expect(
      ungroupForm.getByRole('button', { name: 'Ungroup report' }),
    ).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(
      ungroupForm.getByRole('button', { name: 'Cancel' }),
    ).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(ungroup).toBeFocused()
    await ungroup.dblclick()
    await expect(ungroupForm).toBeVisible()
    await ungroupForm.getByRole('button', { name: 'Cancel' }).click()
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
    for (const name of ['Edit title and summary']) {
      await expectTouchTarget(page.getByRole('button', { name }).first())
    }
    for (const name of [/^Owner:/, new RegExp(`^Assignee for ${title}`)]) {
      const trigger = page.getByRole('combobox', { name })
      await expectTouchTarget(trigger)
      await trigger.click()
      await expectTouchTarget(page.getByRole('option').first())
      expect(await overflow()).toBe(false)
      await page.keyboard.press('Escape')
      await expect(trigger).toBeFocused()
    }
    expect(await overflow()).toBe(false)
    await page.getByRole('link', { name: title }).last().click()
    await expect(triage(page)).toBeVisible()
    expect(await overflow()).toBe(false)
    for (const name of ['Move to problem', 'Move to new problem', 'Ungroup']) {
      await expectTouchTarget(triage(page).getByRole('button', { name }))
    }
    const phoneUngroup = triage(page).getByRole('button', {
      name: 'Ungroup',
      exact: true,
    })
    await phoneUngroup.click()
    const phoneForm = triage(page).getByRole('form', {
      name: 'Ungroup this report?',
    })
    await expectTouchTarget(
      phoneForm.getByRole('button', { name: 'Ungroup report' }),
    )
    await expectTouchTarget(phoneForm.getByRole('button', { name: 'Cancel' }))
    expect(await overflow()).toBe(false)
    await phoneForm.getByRole('button', { name: 'Cancel' }).click()
    await phoneUngroup.dblclick()
    await expect(phoneForm).toBeVisible()
    await phoneForm.getByRole('button', { name: 'Cancel' }).click()
  })
})
