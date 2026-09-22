import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { AxeBuilder } from '@axe-core/playwright'

const seedPath = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  '.auth/seed.json',
)
type Seed = {
  users: { email: string; password: string }[]
  workspace_id: string
  expired_invitation_token: string
}

test('owner signs in and signs out', async ({ page }) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[1].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/sign-in$/)
  await page.goto('/inbox')
  await expect(page).toHaveURL(/\/sign-in$/)
})

test('sign-in is keyboard accessible and has no axe violations', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/sign-in')
  await expect(page).toHaveScreenshot('signin-desktop.png', { fullPage: true })
  const email = page.getByRole('textbox', { name: 'Email' })
  await page.keyboard.press('Tab')
  await expect(email).toBeFocused()
  await page.keyboard.press('Tab')
  await page.getByLabel('Password').fill('temporary')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeFocused()
  const results = await new AxeBuilder({ page }).analyze()
  expect(results.violations).toEqual([])
})

test('sign-in at mobile width', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/sign-in')
  await expect(page).toHaveScreenshot('signin-mobile.png', { fullPage: true })
})

test('expired invitation explains the problem without a password form', async ({
  page,
}) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto(`/invite/${seed.expired_invitation_token}`)
  await expect(page.getByRole('status')).toHaveText(
    'This invitation has expired or is no longer available.',
  )
  await expect(page.getByLabel('Password')).toHaveCount(0)
})

test('a member accepts an invitation in a clean browser context', async ({
  page,
  browser,
}) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  const inviteEmail = `invite-${Date.now()}@example.test`
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[3].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.evaluate(() => fetch('/api/auth/csrf/'))
  const csrfCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'csrftoken',
  )
  const invitationResponse = await page
    .context()
    .request.post(
      new URL(
        `/api/workspaces/${seed.workspace_id}/invitations/`,
        page.url(),
      ).toString(),
      {
        data: { email: inviteEmail, role: 'member' },
        headers: { 'X-CSRFToken': csrfCookie?.value ?? '' },
      },
    )
  expect(invitationResponse.status()).toBe(201)
  const invitation = (await invitationResponse.json()) as { accept_url: string }
  const cleanContext = await browser.newContext({
    baseURL: new URL(page.url()).origin,
  })
  const invitePage = await cleanContext.newPage()
  await invitePage.goto(invitation.accept_url)
  await invitePage.getByLabel('Full name').fill('Invited Member')
  await invitePage
    .getByLabel('Password', { exact: true })
    .fill('Harbour-Copper-7628!Quilt')
  await invitePage
    .getByLabel('Confirm password')
    .fill('Harbour-Copper-7628!Quilt')
  await invitePage.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(invitePage).toHaveURL(/\/inbox$/)
  await invitePage.getByRole('button', { name: 'Sign out' }).click()
  await expect(invitePage).toHaveURL(/\/sign-in$/)
  await invitePage.getByRole('textbox', { name: 'Email' }).fill(inviteEmail)
  await invitePage.getByLabel('Password').fill('Harbour-Copper-7628!Quilt')
  await invitePage.getByRole('button', { name: 'Sign in' }).click()
  await expect(invitePage).toHaveURL(/\/inbox$/)
  await cleanContext.close()
})

test('an owner issued password reset link works in a clean browser context', async ({
  page,
  browser,
}) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[5].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  const session = (await page.evaluate(async () =>
    (await fetch('/api/auth/session/')).json(),
  )) as { memberships: { membership_id: string; workspace: { id: string } }[] }
  await page.evaluate(() => fetch('/api/auth/csrf/'))
  const csrfCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'csrftoken',
  )
  const membership = session.memberships[0]
  const response = await page
    .context()
    .request.post(
      new URL(
        `/api/workspaces/${membership.workspace.id}/memberships/${membership.membership_id}/password-reset/`,
        page.url(),
      ).toString(),
      { headers: { 'X-CSRFToken': csrfCookie?.value ?? '' } },
    )
  expect(response.status()).toBe(201)
  const reset = (await response.json()) as { reset_url: string }
  const context = await browser.newContext({
    baseURL: new URL(page.url()).origin,
  })
  const resetPage = await context.newPage()
  await resetPage.goto(reset.reset_url)
  await resetPage.getByLabel('New password').fill('Cobalt-Window-9264!Birch')
  await resetPage
    .getByLabel('Confirm password')
    .fill('Cobalt-Window-9264!Birch')
  await resetPage.getByRole('button', { name: 'Save password' }).click()
  await expect(resetPage).toHaveURL(/\/inbox$/)
  await resetPage.getByRole('button', { name: 'Sign out' }).click()
  await resetPage
    .getByRole('textbox', { name: 'Email' })
    .fill(seed.users[5].email)
  await resetPage.getByLabel('Password').fill('Cobalt-Window-9264!Birch')
  await resetPage.getByRole('button', { name: 'Sign in' }).click()
  await expect(resetPage).toHaveURL(/\/inbox$/)
  await context.close()
})
