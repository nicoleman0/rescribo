import { expect, test, type Browser, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

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
    await expect(detail(page)).toContainText('Delivery: Sent')

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

    await list(page)
      .getByRole('link', { name: new RegExp(title) })
      .focus()
    await page.keyboard.press('Enter')
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
    expect((await tab.boundingBox())?.height).toBeGreaterThanOrEqual(44)
    await list(page)
      .getByRole('link', { name: new RegExp(title) })
      .click()
    await expect(detail(page)).toBeVisible()
    expect(await overflow(page)).toBe(false)
  })
})
