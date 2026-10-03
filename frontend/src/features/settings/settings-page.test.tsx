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
const unlinked = {
  [`GET ${base}slack/identity/`]: () =>
    json({ linked: false, team_id: '', user_id: '', linked_at: null }),
}
function render() {
  return renderWorkspaceRoutes(
    [{ path: '/settings', element: <SettingsPage /> }],
    '/settings',
  )
}
function owner() {
  testMembership.role = 'owner'
  return stubApi({
    ...unlinked,
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
  testMembership.role = 'member'
  stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json([]),
  })
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
    ...unlinked,
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
    ...unlinked,
    [`GET ${base}connections/`]: () => (failed ? json({}, 503) : json([])),
  })
  render()
  expect(await screen.findByText('Could not load connections')).toBeVisible()
  failed = false
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByRole('heading', { name: 'Slack' })).toBeVisible()
})

const slackConnection = {
  provider: 'slack',
  identity: 'Acme',
  external_id: 'T1',
  status: 'active',
  scopes: [],
  error_code: '',
  error_detail: '',
  last_success_at: null,
  last_reconciled_at: null,
  repository: '',
  visibility: '',
  version: 1,
  channels: [],
  operations: { queued: 0, running: 0, failed: 0, uncertain: 0 },
}

test('a member generates a Slack linking code and sees the link once made', async () => {
  let linked = false
  const fetch = stubApi({
    [`GET ${base}connections/`]: () => json([slackConnection]),
    [`GET ${base}slack/identity/`]: () =>
      json({
        linked,
        team_id: linked ? 'T1' : '',
        user_id: linked ? 'U1' : '',
        linked_at: linked ? '2026-10-01T10:00:00Z' : null,
      }),
    [`POST ${base}slack/link-code/`]: () =>
      json({ code: 'code-123', expires_at: '2026-10-01T10:05:00Z' }),
  })
  render()
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: 'Generate linking code' }),
  )
  expect(await screen.findByLabelText('Linking code')).toHaveValue('code-123')
  linked = true
  await user.click(screen.getByRole('button', { name: 'Generate a new code' }))
  expect(await screen.findByText(/Linked to Slack user/)).toBeVisible()
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method === 'POST'),
  ).toHaveLength(2)
})

test('linking is unavailable until Slack is connected', async () => {
  stubApi({ ...unlinked, [`GET ${base}connections/`]: () => json([]) })
  render()
  expect(
    await screen.findByText(/Slack is not connected to this workspace/),
  ).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Generate linking code' }),
  ).not.toBeInTheDocument()
})
