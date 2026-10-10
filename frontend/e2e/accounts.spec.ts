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
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
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
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[0].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  const memberships = await page
    .context()
    .request.get(`/api/workspaces/${seed.workspace_id}/memberships/`)
  expect(memberships.status()).toBe(200)
  const rows = (await memberships.json()) as { id: string; email: string }[]
  const member = rows.find((row) => row.email === 'member@example.test')
  expect(member).toBeTruthy()
  await page.evaluate(() => fetch('/api/auth/csrf/'))
  const csrfCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'csrftoken',
  )
  const response = await page
    .context()
    .request.post(
      new URL(
        `/api/workspaces/${seed.workspace_id}/memberships/${member!.id}/password-reset/`,
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
    .fill('member@example.test')
  await resetPage.getByLabel('Password').fill('Cobalt-Window-9264!Birch')
  await resetPage.getByRole('button', { name: 'Sign in' }).click()
  await expect(resetPage).toHaveURL(/\/inbox$/)
  await context.close()
})

test('a removed member accepts a new invitation with their password', async ({
  page,
  browser,
}) => {
  const seed = JSON.parse(await readFile(seedPath, 'utf8')) as Seed
  const email = `reinvite-${Date.now()}@example.test`
  const password = 'Harbour-Copper-7628!Quilt'
  await page.goto('/sign-in')
  await page.getByRole('textbox', { name: 'Email' }).fill(seed.users[3].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.evaluate(() => fetch('/api/auth/csrf/'))
  const csrfCookie = (await page.context().cookies()).find(
    (cookie) => cookie.name === 'csrftoken',
  )
  const workspace = `/api/workspaces/${seed.workspace_id}`
  const ownerPost = (path: string, data?: unknown) =>
    page.context().request.post(new URL(path, page.url()).toString(), {
      data,
      headers: { 'X-CSRFToken': csrfCookie?.value ?? '' },
    })
  const invite = async () => {
    const response = await ownerPost(`${workspace}/invitations/`, {
      email,
      role: 'member',
    })
    expect(response.status()).toBe(201)
    return ((await response.json()) as { accept_url: string }).accept_url
  }

  // One browser context throughout, so the second visit carries the cookie of
  // the session that the removal ended.
  const memberContext = await browser.newContext({
    baseURL: new URL(page.url()).origin,
  })
  const member = await memberContext.newPage()
  await member.goto(await invite())
  await member.getByLabel('Full name').fill('Returning Member')
  await member.getByLabel('Password', { exact: true }).fill(password)
  await member.getByLabel('Confirm password').fill(password)
  await member.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(member).toHaveURL(/\/inbox$/)

  const memberships = await page
    .context()
    .request.get(`${workspace}/memberships/`)
  const rows = (await memberships.json()) as { id: string; email: string }[]
  const membership = rows.find((row) => row.email === email)
  expect(membership).toBeTruthy()
  const revoked = await ownerPost(
    `${workspace}/memberships/${membership!.id}/revoke/`,
  )
  expect(revoked.status()).toBe(204)
  await member.goto('/inbox')
  await expect(member).toHaveURL(/\/sign-in$/)

  await member.goto(await invite())
  await expect(
    member.getByText('This email already has an account.'),
  ).toBeVisible()
  await expect(member.getByLabel('Full name')).toHaveCount(0)
  await member.getByLabel('Password').fill('not-the-password')
  await member.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(member.getByRole('alert')).toHaveText('Password is incorrect.')
  await expect(member).toHaveURL(/\/invite\//)
  await member.getByLabel('Password').fill(password)
  await member.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(member).toHaveURL(/\/inbox$/)

  const session = await memberContext.request.get('/api/auth/session/')
  expect(session.status()).toBe(200)
  const { memberships: active } = (await session.json()) as {
    memberships: { role: string; workspace: { id: string } }[]
  }
  expect(active.map((item) => [item.workspace.id, item.role])).toEqual([
    [seed.workspace_id, 'member'],
  ])
  await member.getByRole('button', { name: 'Sign out' }).click()
  await expect(member).toHaveURL(/\/sign-in$/)
  await member.getByRole('textbox', { name: 'Email' }).fill(email)
  await member.getByLabel('Password').fill(password)
  await member.getByRole('button', { name: 'Sign in' }).click()
  await expect(member).toHaveURL(/\/inbox$/)
  await memberContext.close()
})
