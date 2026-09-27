import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import {
  json,
  renderWorkspaceRoutes,
  stubApi,
  testMembership,
} from '@/test/render'
import { SettingsPage } from './settings-page'

const base = '/api/workspaces/ws-1/'
function render() {
  return renderWorkspaceRoutes(
    [{ path: '/settings', element: <SettingsPage /> }],
    '/settings',
  )
}
function owner() {
  testMembership.role = 'owner'
  return stubApi({
    [`GET ${base}connections/`]: () => json([]),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
  })
}
afterEach(() => {
  testMembership.role = 'member'
  vi.unstubAllGlobals()
})

test('members see connections but no owner controls', async () => {
  stubApi({ [`GET ${base}connections/`]: () => json([]) })
  render()
  expect(await screen.findByRole('heading', { name: 'GitHub' })).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Delete workspace' }),
  ).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Invite email')).not.toBeInTheDocument()
  expect(screen.queryByText(/AI setting/i)).not.toBeInTheDocument()
})

test('workspace deletion requires the exact slug and cancellation makes no request', async () => {
  const fetch = owner()
  render()
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: 'Delete workspace' }),
  )
  const form = screen.getByRole('form', { name: 'Delete workspace' })
  expect(within(form).getByText(/Backups expire/)).toBeVisible()
  expect(
    within(form).getByRole('button', { name: 'Delete workspace' }),
  ).toBeDisabled()
  await user.type(
    within(form).getByLabelText('Type example to confirm'),
    'wrong',
  )
  expect(
    within(form).getByRole('button', { name: 'Delete workspace' }),
  ).toBeDisabled()
  await user.clear(within(form).getByLabelText('Type example to confirm'))
  await user.type(
    within(form).getByLabelText('Type example to confirm'),
    'example',
  )
  expect(
    within(form).getByRole('button', { name: 'Delete workspace' }),
  ).toBeEnabled()
  await user.click(within(form).getByRole('button', { name: 'Cancel' }))
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(
    true,
  )
})

test('invitation failure preserves the entered email', async () => {
  testMembership.role = 'owner'
  stubApi({
    [`GET ${base}connections/`]: () => json([]),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
    [`POST ${base}invitations/`]: () =>
      json({ detail: 'Try again later.', reason: 'throttled' }, 429),
  })
  render()
  const user = userEvent.setup()
  await user.type(
    await screen.findByLabelText('Invite email'),
    'new@example.test',
  )
  await user.click(screen.getByRole('button', { name: 'Create invitation' }))
  expect(await screen.findByText('Try again later.')).toBeVisible()
  expect(screen.getByLabelText('Invite email')).toHaveValue('new@example.test')
})

test('connection query can recover after retry', async () => {
  let failed = true
  stubApi({
    [`GET ${base}connections/`]: () => (failed ? json({}, 503) : json([])),
  })
  render()
  expect(await screen.findByText('Could not load connections')).toBeVisible()
  failed = false
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { name: 'Slack' })).toBeVisible()
})
