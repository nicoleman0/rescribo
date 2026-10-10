import { expect, test, type Browser, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'
import { expectTouchTarget } from './touch-target.js'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
const seedPath = path.join(authDir, 'seed.json')
const sessionPath = path.join(authDir, 'follow-ups-owner.json')
type Seed = { users: { email: string; password: string }[] }

// Sign in once and reuse the session: login is throttled per identity and
// address. No other spec signs in as this owner or changes its password.
async function saveSession(browser: Browser, baseURL?: string) {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  const page = await browser.newPage({
    baseURL,
    storageState: { cookies: [], origins: [] },
  })
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[5].email)
  await page.getByLabel('Password').fill(seed.users[5].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.context().storageState({ path: sessionPath })
  await page.close()
}

const list = (page: Page) => page.getByRole('list', { name: 'Follow-ups' })
const detail = (page: Page) =>
  page.getByRole('region', { name: 'Follow-up detail' })
const message = (page: Page) =>
  detail(page).getByRole('region', { name: 'Message' })

async function confirmFix(page: Page, marker: string) {
  await page.goto('/inbox/new')
  const title = `Follow-up ${marker}`
  await page.getByLabel('Title').fill(title)
  await page.getByLabel('Customer organisation').fill(`Customer ${marker}`)
  await page.getByRole('button', { name: 'Create report' }).click()
  await expect(
    page
      .getByRole('region', { name: 'Report detail' })
      .getByRole('heading', { name: title }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Create problem' }).click()
  await page.getByLabel('Problem title').fill(`Problem ${marker}`)
  await page.getByRole('button', { name: 'Create and link' }).click()
  await page
    .getByRole('region', { name: 'Report detail' })
    .getByRole('link', { name: `Problem ${marker}` })
    .click()
  await expect(
    page.getByRole('heading', { level: 1, name: `Problem ${marker}` }),
  ).toBeVisible()
  await page.getByLabel('Fix details').fill(`A fix for ${marker}`)
  await page.getByLabel('Available in version').fill(`1.${Date.now() % 10}`)
  await page.getByRole('button', { name: 'Confirm fix', exact: true }).click()
  await expect(
    page.getByRole('region', { name: 'Confirmed fix' }),
  ).toContainText(marker)
  return title
}

async function ensureFollowUpOwner(page: Page) {
  await page.goto('/inbox')
  const signInHeading = page.getByRole('heading', { name: 'Sign in' })
  await expect(
    signInHeading.or(page.getByRole('heading', { name: 'Inbox' })),
  ).toBeVisible()
  if (await signInHeading.isVisible().catch(() => false)) {
    const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
    await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[5].email)
    await page.getByLabel('Password').fill(seed.users[5].password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/inbox$/)
  }
}

async function openFollowUp(page: Page, title: string) {
  await page.goto('/follow-ups?bucket=needs_approval')
  await list(page)
    .getByRole('link', { name: new RegExp(title) })
    .click()
  await expect(detail(page).getByRole('heading', { name: title })).toBeVisible()
}

async function overflow(page: Page) {
  return page.evaluate<boolean>(
    'document.documentElement.scrollWidth > window.innerWidth',
  )
}

test.describe('Follow-ups', () => {
  test.beforeAll(async ({ browser }, info) =>
    saveSession(browser, info.project.use.baseURL),
  )
  test.use({ storageState: sessionPath })

  test('delivers an approved fix to Slack and records the customer outcome', async ({
    page,
  }) => {
    const marker = `Slack ${Date.now()}`
    const title = await confirmFix(page, marker)

    await openFollowUp(page, title)
    await expect(detail(page)).toContainText(`Customer ${marker}`)
    await expect(detail(page)).toContainText('Not prepared')
    await expect(
      message(page).getByRole('button', { name: 'Send to Slack' }),
    ).toHaveCount(0)

    await message(page).getByRole('button', { name: 'Prepare message' }).click()
    const editor = message(page).getByLabel('Message')
    await expect(editor).toBeEnabled()
    // The saved edit is the exact message that goes out.
    await editor.fill(`Hi, ${title} is fixed. Reply here if anything broke.`)
    await message(page).getByRole('button', { name: 'Save edits' }).click()
    await expect(
      message(page).getByRole('button', { name: 'Save edits' }),
    ).toBeDisabled()
    await expect(detail(page)).toContainText(
      'Hi, Follow-up ' + marker + ' is fixed.',
    )

    await message(page).getByRole('button', { name: 'Send to Slack' }).click()
    // The worker may finish before refresh, so only the end state is asserted.
    await expect(detail(page).getByText('Message sent')).toBeVisible({
      timeout: 15_000,
    })
    await expect(
      detail(page).getByRole('term').filter({ hasText: 'Delivery' }),
    ).toBeVisible()
    await expect(
      detail(page).getByRole('definition').filter({ hasText: /^Sent/ }),
    ).toBeVisible()

    const contact = page.getByRole('region', { name: 'Customer contact' })
    await detail(page)
      .getByLabel('Record outcome')
      .selectOption({ label: 'Customer contacted' })
    await contact.getByRole('button', { name: 'Record outcome' }).click()
    await expect(contact).toContainText('Outcome: Contacted.')

    await detail(page)
      .getByLabel('Record outcome')
      .selectOption({ label: 'Customer confirmed' })
    await contact.getByRole('button', { name: 'Record outcome' }).click()
    await expect(contact).toContainText('Outcome: Confirmed.')

    // The outcome moves the follow-up between buckets.
    await page.goto('/follow-ups')
    await page.getByRole('button', { name: /Completed/ }).click()
    await expect(
      list(page).getByRole('link', { name: new RegExp(title) }),
    ).toBeVisible()
    await page.getByRole('button', { name: /Needs approval/ }).click()
    await expect(
      list(page).getByRole('link', { name: new RegExp(title) }),
    ).toHaveCount(0)
  })

  test('records an outcome on an unlinked Slack recipient without sending', async ({
    browser,
  }, info) => {
    const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
    const memberPage = await browser.newPage({
      baseURL: info.project.use.baseURL as string,
    })
    await memberPage.goto('/sign-in')
    await memberPage
      .getByRole('textbox', { name: 'Email' })
      .fill(seed.users[7].email)
    await memberPage.getByLabel('Password').fill(seed.users[7].password)
    await memberPage.getByRole('button', { name: 'Sign in' }).click()
    await expect(memberPage).toHaveURL(/\/inbox$/)

    const marker = `Manual journey ${Date.now()}`
    const title = await confirmFix(memberPage, marker)
    await openFollowUp(memberPage, title)

    await message(memberPage)
      .getByRole('button', { name: 'Prepare message' })
      .click()
    await expect(
      message(memberPage).getByRole('button', { name: 'Copy message' }),
    ).toBeVisible()
    await expect(detail(memberPage)).toContainText('has no Slack link')
    await message(memberPage)
      .getByRole('button', { name: 'Copy message' })
      .click()
    // Delivery and contact state stay independent: nothing enforces a wait.
    await detail(memberPage)
      .getByLabel('Record outcome')
      .selectOption({ label: 'Customer contacted' })
    await detail(memberPage)
      .getByRole('region', { name: 'Customer contact' })
      .getByRole('button', { name: 'Record outcome' })
      .click()
    await expect(
      detail(memberPage).getByText('Outcome: Contacted.'),
    ).toBeVisible()

    await memberPage.goto('/follow-ups')
    await memberPage
      .getByRole('button', { name: /Awaiting confirmation/ })
      .click()
    await expect(
      list(memberPage).getByRole('link', { name: new RegExp(title) }),
    ).toBeVisible()
    await memberPage.close()
  })

  test('opens a follow-up as a full page and returns to its bucket', async ({
    page,
  }) => {
    await ensureFollowUpOwner(page)
    const marker = `Full page ${Date.now()}`
    const title = await confirmFix(page, marker)
    await openFollowUp(page, title)
    const followUpId = new URL(page.url()).pathname.split('/').at(-1)
    await detail(page).getByRole('button', { name: 'Prepare message' }).click()
    await expect(
      detail(page).getByRole('textbox', { name: 'Message' }),
    ).toBeVisible()

    await detail(page).getByRole('link', { name: 'Open full page' }).click()
    await expect(page).toHaveURL(
      new RegExp(`/follow-ups/${followUpId}/page\\?bucket=needs_approval$`),
    )
    await expect(
      page.getByRole('heading', { level: 1, name: title }),
    ).toBeVisible()
    await expect(list(page)).toHaveCount(0)

    const contact = page.getByRole('region', { name: 'Customer contact' })
    await contact.getByLabel('Record outcome').selectOption({
      label: 'Customer contacted',
    })
    await contact.getByRole('button', { name: 'Record outcome' }).click()
    await expect(contact).toContainText('Outcome: Contacted.')
    await expect(page.getByRole('region', { name: 'History' })).toContainText(
      'recorded the outcome',
    )
    expect(await axeViolations(page)).toEqual([])

    await page.setViewportSize({ width: 375, height: 812 })
    expect(await overflow(page)).toBe(false)
    await page.getByRole('link', { name: 'Back to follow-ups' }).click()
    await expect(page).toHaveURL(/\/follow-ups\?bucket=needs_approval$/)
    await expect(
      page.getByRole('heading', { level: 1, name: 'Follow-ups' }),
    ).toBeVisible()
    await expect(
      page.getByRole('navigation', { name: 'Follow-up buckets' }),
    ).toBeVisible()
  })

  test('records contact and then confirmation without touching the form again', async ({
    page,
  }) => {
    await ensureFollowUpOwner(page)
    const marker = `Second outcome ${Date.now()}`
    const title = await confirmFix(page, marker)
    await openFollowUp(page, title)
    // The contact section appears once the message is prepared. Nothing is sent.
    await detail(page).getByRole('button', { name: 'Prepare message' }).click()
    await expect(
      detail(page).getByRole('textbox', { name: 'Message' }),
    ).toBeVisible()
    const contact = page.getByRole('region', { name: 'Customer contact' })
    const record = contact.getByRole('button', { name: 'Record outcome' })
    await contact.getByLabel('Note').fill('Called the customer')
    await record.click()
    await expect(contact).toContainText('Outcome: Contacted.')
    await expect(contact.getByLabel('Record outcome')).toHaveValue('confirmed')
    // No selectOption: the form must send the option the dropdown shows.
    const [request] = await Promise.all([
      page.waitForRequest(
        (sent) => sent.method() === 'POST' && sent.url().endsWith('/outcome/'),
      ),
      record.click(),
    ])
    expect(request.postDataJSON()).toMatchObject({
      state: 'confirmed',
      note: '',
    })
    await expect(contact).toContainText('Outcome: Confirmed.')
  })

  test('marks a problem reviewed after a customer is still affected', async ({
    page,
  }) => {
    await ensureFollowUpOwner(page)
    const marker = `Review ${Date.now()}`
    const title = await confirmFix(page, marker)
    const problemUrl = page.url()
    await openFollowUp(page, title)
    // The contact section appears once the message is prepared. Nothing is sent.
    await detail(page).getByRole('button', { name: 'Prepare message' }).click()
    await expect(
      detail(page).getByRole('textbox', { name: 'Message' }),
    ).toBeVisible()
    const contact = page.getByRole('region', { name: 'Customer contact' })
    await contact
      .getByLabel('Record outcome')
      .selectOption({ label: 'Still affected' })
    await contact.getByRole('button', { name: 'Record outcome' }).click()
    await expect(contact).toContainText('Outcome: Still affected.')

    await page.goto(problemUrl)
    await expect(
      page.getByRole('heading', { level: 2, name: 'Review the fix' }),
    ).toBeVisible()
    await expect(page.getByText('Needs review').first()).toBeVisible()
    await page.getByRole('button', { name: 'Mark reviewed' }).click()
    await expect(
      page.getByRole('heading', { level: 2, name: /^Fix available in/ }),
    ).toBeVisible()
    await expect(page.getByText('Needs review')).toHaveCount(0)
    await expect(
      page.getByRole('list', { name: 'Problem activity' }),
    ).toContainText('marked the problem reviewed')
  })

  test('is keyboard operable, accessible, and fits a phone', async ({
    page,
  }) => {
    await ensureFollowUpOwner(page)
    const marker = `Keyboard ${Date.now()}`
    const title = await confirmFix(page, marker)

    await page.goto('/follow-ups')
    await expect(list(page)).toBeVisible()
    expect(await axeViolations(page)).toEqual([])

    await page.getByRole('button', { name: /Needs approval/ }).focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/bucket=needs_approval/)
    await page.getByRole('button', { name: /All/ }).focus()
    await page.keyboard.press('Enter')

    const allTab = page.getByRole('button', { name: /All/ })
    await expect(allTab).toHaveAttribute('aria-pressed', 'true')
    await expect(list(page)).toBeVisible()
    await expect(list(page).locator('xpath=..')).not.toHaveAttribute(
      'aria-busy',
      'true',
    )
    const followUpLink = list(page).getByRole('link', {
      name: new RegExp(title),
    })
    await expect(followUpLink).toBeVisible()
    await followUpLink.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/follow-ups\/[^/?]+(?:\?.*)?$/)
    await expect(
      detail(page).getByRole('heading', { name: title }),
    ).toBeVisible()
    expect(await axeViolations(page)).toEqual([])

    await detail(page).getByRole('link', { name: 'Back to follow-ups' }).focus()
    await page.keyboard.press('Enter')
    await expect(list(page)).toBeVisible()

    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/follow-ups?bucket=needs_approval')
    await expect(list(page)).toBeVisible()
    expect(await overflow(page)).toBe(false)
    const tab = page.getByRole('button', { name: /Needs approval/ })
    await expectTouchTarget(tab)
    await list(page)
      .getByRole('link', { name: new RegExp(title) })
      .click()
    await expect(detail(page)).toBeVisible()
    expect(await overflow(page)).toBe(false)
  })
})
