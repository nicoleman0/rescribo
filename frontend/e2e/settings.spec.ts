import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { axeViolations } from './axe.js'

const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')
test('owner manages invitations, members and confirmed deletion on desktop and mobile', async ({
  page,
  browser,
}, testInfo) => {
  const seed = JSON.parse(
    await readFile(path.join(authDir, 'seed.json'), 'utf8'),
  ) as {
    users: { email: string; password: string }[]
    settings_workspace_id: string
  }
  await page.goto('/sign-in')
  await page.getByLabel('Email').fill(seed.users[9].email)
  await page.getByLabel('Password').fill(seed.users[9].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.goto('/settings')
  await expect(page).toHaveTitle('Settings · Rescribo')
  await expect(
    page.getByRole('heading', { name: 'Members and invitations' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Make member', exact: true }).click()
  await expect(page.getByText(/At least one active owner/i)).toBeVisible()
  await page
    .getByLabel('Invite email')
    .fill(`settings-${Date.now()}@example.test`)
  await page.getByRole('button', { name: 'Create invitation' }).click()
  const invite = await page.getByLabel('Invitation link').inputValue()
  const invitePath = new URL(invite).pathname
  const member = await browser.newPage({
    baseURL: testInfo.project.use.baseURL,
  })
  await member.goto(invitePath)
  await member.getByLabel('Full name').fill('Settings Member')
  await member
    .getByLabel('Password', { exact: true })
    .fill('Settings-member-2026!')
  await member.getByLabel('Confirm password').fill('Settings-member-2026!')
  await member.getByRole('button', { name: 'Accept invitation' }).click()
  await expect(member).toHaveURL(/\/inbox$/)
  await member.goto('/settings')
  await expect(
    member.getByText(
      'Workspace owners manage invitations, members, connections and deletion.',
    ),
  ).toBeVisible()
  await expect(
    member.getByRole('button', { name: 'Delete workspace', exact: true }),
  ).toHaveCount(0)
  await member.close()
  await page.reload()
  await expect(page.getByText('Settings Member', { exact: true })).toBeVisible()
  await expect(await axeViolations(page)).toEqual([])
  await page.screenshot({
    path: testInfo.outputPath('settings-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(await axeViolations(page)).toEqual([])
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath('settings-mobile.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: 'Make owner', exact: true }).click()
  await expect(
    page.getByRole('button', { name: 'Make member', exact: true }),
  ).toHaveCount(2)
  await page.goto('/inbox/new')
  await page
    .getByLabel('Title', { exact: true })
    .fill('Delete this settings test report')
  await page.getByRole('button', { name: 'Create report' }).click()
  await expect(
    page.getByRole('heading', { name: 'Delete this settings test report' }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Delete report', exact: true }).click()
  const reportForm = page.getByRole('form', { name: 'Delete report' })
  await expect(
    reportForm.getByRole('button', { name: 'Delete report', exact: true }),
  ).toBeDisabled()
  await reportForm.getByLabel('Type DELETE to confirm').fill('DELETE')
  await reportForm
    .getByRole('button', { name: 'Delete report', exact: true })
    .click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.goto('/settings')
  await page
    .getByRole('button', { name: 'Delete workspace', exact: true })
    .click()
  const form = page.getByRole('form', { name: 'Delete workspace' })
  await expect(form.getByText(/Backups expire/)).toBeVisible()
  await form.getByLabel('Type e2e-settings to confirm').fill('e2e-settings')
  await form
    .getByRole('button', { name: 'Delete workspace', exact: true })
    .click()
  await expect(
    page.getByRole('heading', {
      name: /Workspace access removed|Sign in/i,
    }),
  ).toBeVisible()
})

test('a long member email does not overflow settings at 320px', async ({
  page,
}) => {
  const seed = JSON.parse(
    await readFile(path.join(authDir, 'seed.json'), 'utf8'),
  ) as { users: { email: string; password: string }[] }
  await page.goto('/sign-in')
  await page.getByLabel('Email').fill(seed.users[1].email)
  await page.getByLabel('Password').fill(seed.users[0].password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/inbox$/)
  await page.route('**/api/workspaces/*/memberships/', async (route) => {
    const response = await route.fetch()
    const members = (await response.json()) as { id: string; email: string }[]
    members.push({
      ...members[0],
      id: 'long-email-member',
      email: 'invite-0000000000000-with-a-long-name@example.test',
    })
    await route.fulfill({ response, json: members })
  })
  await page.setViewportSize({ width: 320, height: 740 })
  await page.goto('/settings')
  await expect(
    page.getByRole('button', { name: /^Remove invite-0000000000000/ }),
  ).toBeVisible()
  expect(
    await page.evaluate('document.documentElement.scrollWidth <= innerWidth'),
  ).toBe(true)
})
