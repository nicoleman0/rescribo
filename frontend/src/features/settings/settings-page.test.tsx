import {
  fireEvent,
  render as rtlRender,
  screen,
  within,
} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Navigate, Route, Routes } from 'react-router-dom'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { LocationProbe } from '@/test/location-probe'
import { formatDate } from '@/features/inbox/report-format'
import { json, stubApi, testMembership } from '@/test/render'
import { SettingsPage } from './settings-page'
import {
  AppearanceSection,
  ConnectionsSection,
  MembersSection,
  SlackAccountSection,
  WorkspaceSection,
} from './settings-sections'

const base = '/api/workspaces/ws-1/'
const notManaged = () =>
  json({ managed: false, api_style: '', base_url: '', model: '' })
// Every Connections render also asks whether the deployment sets the model.
const unlinked = {
  [`GET ${base}slack/identity/`]: () =>
    json({ linked: false, team_id: '', user_id: '', linked_at: null }),
  [`GET ${base}connections/model/deployment/`]: notManaged,
}
function render(path = '/settings/connections') {
  return rtlRender(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <WorkspaceProvider membership={testMembership}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/settings" element={<SettingsPage />}>
              <Route index element={<Navigate replace to="appearance" />} />
              <Route path="appearance" element={<AppearanceSection />} />
              <Route path="members" element={<MembersSection />} />
              <Route path="connections" element={<ConnectionsSection />} />
              <Route path="slack-account" element={<SlackAccountSection />} />
              <Route path="workspace" element={<WorkspaceSection />} />
            </Route>
          </Routes>
          <LocationProbe />
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
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
  testMembership.workspace.is_demo = false
  vi.unstubAllGlobals()
})

test('members see connections but no owner controls', async () => {
  testMembership.role = 'member'
  const fetch = stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json([]),
  })
  render()
  // The named role query is slow under load: wait on text, then check the role once.
  await screen.findByText('GitHub', { selector: 'h2' })
  expect(screen.getByRole('heading', { name: 'GitHub' })).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Delete workspace' }),
  ).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Invite email')).not.toBeInTheDocument()
  expect(screen.queryByText(/AI setting/i)).not.toBeInTheDocument()
  expect(
    fetch.mock.calls.some(([input]) => String(input).endsWith('/channels/')),
  ).toBe(false)
})

test('the settings navigation marks the section and filters owner sections', async () => {
  owner()
  render('/settings/appearance')
  const nav = screen.getByRole('navigation', { name: 'Settings sections' })
  expect(within(nav).getAllByRole('link')).toHaveLength(5)
  expect(within(nav).getByRole('link', { name: 'Appearance' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  testMembership.role = 'member'
  render('/settings/workspace')
  const memberNav = screen
    .getAllByRole('navigation', { name: 'Settings sections' })
    .at(-1)!
  expect(within(memberNav).getAllByRole('link')).toHaveLength(3)
  expect(
    within(memberNav).queryByRole('link', { name: 'Members' }),
  ).not.toBeInTheDocument()
  expect(
    await screen.findAllByText(
      'Workspace owners manage invitations, members, connections and deletion.',
    ),
  ).toHaveLength(1)
  expect(
    screen.queryByRole('button', { name: 'Delete workspace' }),
  ).not.toBeInTheDocument()
})

test.each(['/settings/members', '/settings/workspace'])(
  'a member opening %s sees the owner note without controls',
  async (path) => {
    testMembership.role = 'member'
    render(path)
    expect(
      await screen.findByText(
        'Workspace owners manage invitations, members, connections and deletion.',
      ),
    ).toBeVisible()
    expect(screen.queryByLabelText('Invite email')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Delete workspace' }),
    ).not.toBeInTheDocument()
  },
)

test('opening /settings redirects to the Appearance section', async () => {
  testMembership.role = 'member'
  stubApi({ ...unlinked })
  render('/settings')
  expect(await screen.findByRole('group', { name: 'Theme' })).toBeVisible()
  expect(screen.getByTestId('location')).toHaveTextContent(
    '/settings/appearance',
  )
})

test('workspace deletion requires the exact slug and cancellation makes no request', async () => {
  const fetch = owner()
  render('/settings/workspace')
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
  render('/settings/members')
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
  api_style: '',
  base_url: '',
  model: '',
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
  render('/settings/slack-account')
  const user = userEvent.setup()
  await user.click(
    await screen.findByRole('button', { name: 'Generate linking code' }),
  )
  expect(await screen.findByLabelText('Linking code')).toHaveValue('code-123')
  expect(screen.getByText(/Link Rescribo account/)).toBeVisible()
  expect(screen.queryByText(/Submit customer feedback/)).not.toBeInTheDocument()
  linked = true
  await user.click(screen.getByRole('button', { name: 'Generate a new code' }))
  expect(await screen.findByText(/Your Slack account is linked/)).toBeVisible()
  expect(screen.getByText(/Linked since/)).toBeVisible()
  expect(screen.queryByText('U1')).not.toBeInTheDocument()
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method === 'POST'),
  ).toHaveLength(2)
})

test('an owner can expand Slack account technical details', async () => {
  testMembership.role = 'owner'
  stubApi({
    [`GET ${base}connections/`]: () => json([slackConnection]),
    [`GET ${base}slack/identity/`]: () =>
      json({
        linked: true,
        team_id: 'T1',
        user_id: 'U1',
        linked_at: '2026-10-01T10:00:00Z',
      }),
    [`GET ${base}channels/`]: () => json({ channels: [], truncated: false }),
  })
  render('/settings/slack-account')
  expect(await screen.findByText(/Your Slack account is linked/)).toBeVisible()
  const details = screen.getByText('Technical details').closest('details')!
  expect(details).not.toHaveAttribute('open')
  await userEvent.click(within(details).getByText('Technical details'))
  expect(within(details).getByText('U1')).toBeVisible()
  expect(within(details).getByText('T1')).toBeVisible()
})

test('linking is unavailable until Slack is connected', async () => {
  stubApi({ ...unlinked, [`GET ${base}connections/`]: () => json([]) })
  render('/settings/slack-account')
  expect(
    await screen.findByText(/Slack is not connected to this workspace/),
  ).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Generate linking code' }),
  ).not.toBeInTheDocument()
})

test('the demo explains that integrations are disabled', async () => {
  testMembership.workspace.is_demo = true
  try {
    stubApi({
      [`GET ${base}slack/identity/`]: () =>
        json({
          linked: true,
          team_id: 'TDEMO',
          user_id: 'UDEMO',
          linked_at: null,
        }),
      [`GET ${base}connections/`]: () =>
        json([
          slackConnection,
          { ...slackConnection, provider: 'github', identity: 'demo' },
        ]),
      [`GET ${base}connections/model/deployment/`]: notManaged,
    })
    render('/settings/connections')
    const notice = await screen.findByRole('note')
    expect(notice).toHaveTextContent('Integrations are disabled in the demo')
    expect(notice).toHaveTextContent('Nothing is sent to Slack or GitHub.')
    expect(await screen.findAllByText('Disabled in demo')).toHaveLength(3)
    expect(screen.queryByText('UDEMO')).not.toBeInTheDocument()
    render('/settings/slack-account')
    expect(
      await screen.findByText(/Your Slack account is linked/),
    ).toBeVisible()
    expect(screen.queryByText('UDEMO')).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Unlink Slack account' }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Generate linking code' }),
    ).not.toBeInTheDocument()
  } finally {
    testMembership.workspace.is_demo = false
  }
})

test('a member picks a theme that applies at once and is saved', async () => {
  stubApi({ ...unlinked, [`GET ${base}connections/`]: () => json([]) })
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
  localStorage.clear()
  render('/settings/appearance')
  const theme = screen.getByRole('group', { name: 'Theme' })
  expect(within(theme).getByRole('radio', { name: 'System' })).toBeChecked()
  await userEvent.click(within(theme).getByRole('radio', { name: 'Dark' }))
  expect(within(theme).getByRole('radio', { name: 'Dark' })).toBeChecked()
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(localStorage.getItem('rescribo-theme')).toBe('dark')
  localStorage.clear()
})

test('each integration is a card with its status, repository, and job counts', async () => {
  stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () =>
      json([
        {
          ...slackConnection,
          status: 'error',
          last_success_at: '2026-10-01T10:00:00Z',
          error_code: 'token_revoked',
          error_detail: 'Reconnect Slack.',
        },
        {
          ...slackConnection,
          provider: 'github',
          identity: 'acme-app',
          external_id: '42',
          repository: 'acme/web',
          visibility: 'private',
          operations: { queued: 2, running: 1, failed: 3, uncertain: 4 },
        },
      ]),
  })
  render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  expect(within(slack).getByText('Needs attention')).toHaveAttribute(
    'data-tone',
    'danger',
  )
  expect(within(slack).getByText('Reconnect Slack.')).toBeVisible()
  expect(within(slack).getByText('Slack workspace')).toBeVisible()
  expect(within(slack).getByText('Acme')).toBeVisible()
  expect(
    within(slack).getByText(formatDate('2026-10-01T10:00:00Z')),
  ).toBeVisible()
  expect(within(slack).queryByText('T1')).not.toBeInTheDocument()
  const github = screen.getByRole('region', { name: 'GitHub' })
  expect(within(github).getByText('Connected')).toHaveAttribute(
    'data-tone',
    'success',
  )
  expect(within(github).getByText('acme/web')).toBeVisible()
  expect(within(github).getByText('Private')).toBeVisible()
  expect(within(github).getByText('GitHub account')).toBeVisible()
  expect(within(github).getAllByText('Not yet')).toHaveLength(2)
  const jobs = within(github).getByRole('group', { name: 'Jobs' })
  const count = (label: string) =>
    within(jobs).getByText(label).nextElementSibling
  expect(count('Queued')).toHaveTextContent('2')
  expect(count('Running')).toHaveTextContent('1')
  expect(count('Failed')).toHaveTextContent('3')
  expect(count('Uncertain')).toHaveTextContent('4')
})

test('owners can expand technical details while members cannot see them', async () => {
  testMembership.role = 'owner'
  stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () =>
      json([
        {
          ...slackConnection,
          scopes: ['commands'],
          last_success_at: '2026-10-01T10:00:00Z',
          error_code: 'missing_scope',
        },
        {
          ...slackConnection,
          provider: 'github',
          external_id: '42',
          repository: 'acme/web',
          visibility: 'private',
        },
      ]),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
    [`GET ${base}channels/`]: () => json({ channels: [], truncated: false }),
  })
  const ownerView = render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  const details = within(slack)
    .getByText('Technical details')
    .closest('details')!
  expect(details).not.toHaveAttribute('open')
  await userEvent.click(within(details).getByText('Technical details'))
  expect(within(details).getByText('T1')).toBeVisible()
  expect(within(details).getByText('commands')).toBeVisible()
  expect(within(details).getByText('missing_scope')).toBeVisible()
  const github = screen.getByRole('region', { name: 'GitHub' })
  const githubDetails = within(github)
    .getByText('Technical details')
    .closest('details')!
  await userEvent.click(within(githubDetails).getByText('Technical details'))
  expect(within(githubDetails).getByText('42')).toBeVisible()
  expect(
    within(githubDetails).getByText('Last issue sync').nextElementSibling,
  ).toHaveTextContent('None')
  ownerView.unmount()
  testMembership.role = 'member'
  stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json([slackConnection]),
  })
  render()
  expect(await screen.findByRole('region', { name: 'Slack' })).toBeVisible()
  expect(screen.queryByText('Technical details')).not.toBeInTheDocument()
})

test('a provider that was never connected reads not connected', async () => {
  stubApi({ ...unlinked, [`GET ${base}connections/`]: () => json([]) })
  render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  expect(within(slack).getByText('Not connected')).toHaveAttribute(
    'data-tone',
    'neutral',
  )
})

// Answers as the API does with no OAuth application configured, so the
// form does not navigate away.
function ownerWithSetup(provider: 'slack' | 'github', connections: unknown[]) {
  testMembership.role = 'owner'
  return stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json(connections),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
    [`POST ${base}connections/${provider}/setup/`]: () =>
      json(
        {
          detail: 'Ask the operator.',
          reason: 'operator_setup',
          field_errors: {},
        },
        400,
      ),
  })
}
function setupBodies(fetch: ReturnType<typeof stubApi>) {
  return fetch.mock.calls
    .filter(([input]) => String(input).endsWith('/setup/'))
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
}

test.each([
  ['Connect Slack', []],
  ['Reconnect Slack', [slackConnection]],
])('%s sends consent without a repository', async (button, connections) => {
  const fetch = ownerWithSetup('slack', connections)
  render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  const user = userEvent.setup()
  await user.click(within(slack).getByRole('checkbox'))
  await user.click(within(slack).getByRole('button', { name: button }))
  expect(await within(slack).findByText('Ask the operator.')).toBeVisible()
  expect(setupBodies(fetch)).toEqual([{ consent: true }])
})

test('Connect GitHub sends the repository with consent', async () => {
  const fetch = ownerWithSetup('github', [])
  render()
  const github = await screen.findByRole('region', { name: 'GitHub' })
  const user = userEvent.setup()
  await user.type(
    within(github).getByLabelText('GitHub repository'),
    'acme/web',
  )
  await user.click(within(github).getByRole('checkbox'))
  await user.click(
    within(github).getByRole('button', { name: 'Connect GitHub' }),
  )
  expect(await within(github).findByText('Ask the operator.')).toBeVisible()
  expect(setupBodies(fetch)).toEqual([
    { repository: 'acme/web', consent: true },
  ])
})

// Connection check result
const githubConnection = {
  ...slackConnection,
  provider: 'github',
  repository: 'acme/app',
}
const pass = () => new Response(null, { status: 204 })
const missingScopes = () =>
  json(
    {
      detail: 'Grant the required Slack scopes and reconnect.',
      reason: 'missing_scopes',
      field_errors: {},
    },
    400,
  )
function ownerWithConnection(
  connection: () => unknown,
  extra: Record<string, () => Response>,
) {
  testMembership.role = 'owner'
  return stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json([connection()]),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
    [`GET ${base}channels/`]: () => json({ channels: [], truncated: false }),
    ...extra,
  })
}

test('a passing GitHub check says the connection works, with the time', async () => {
  const fetch = ownerWithConnection(() => githubConnection, {
    [`POST ${base}connections/github/refresh/`]: pass,
  })
  render()
  const github = await screen.findByRole('region', { name: 'GitHub' })
  await userEvent.click(
    within(github).getByRole('button', { name: 'Check GitHub status' }),
  )
  const status = within(github).getByRole('status')
  expect(
    await within(status).findByText(/GitHub connection is working/),
  ).toBeVisible()
  expect(status.querySelector('time')).not.toBeNull()
  const post = fetch.mock.calls.find(([, init]) => init?.method === 'POST')
  expect(JSON.parse(String(post?.[1]?.body))).toEqual({ version: 1 })
})

test('a repeated check shows a different time', async () => {
  vi.useFakeTimers({ toFake: ['Date'] })
  try {
    vi.setSystemTime(new Date('2026-01-01T10:00:00Z'))
    ownerWithConnection(() => githubConnection, {
      [`POST ${base}connections/github/refresh/`]: pass,
    })
    render()
    const github = await screen.findByRole('region', { name: 'GitHub' })
    const user = userEvent.setup({ advanceTimers: () => {} })
    const press = () =>
      user.click(
        within(github).getByRole('button', { name: 'Check GitHub status' }),
      )
    const stamp = async () => {
      const status = within(github).getByRole('status')
      const time = await within(status).findByText(/./, {
        selector: 'time',
      })
      return time.getAttribute('datetime')
    }
    await press()
    const first = await stamp()
    vi.setSystemTime(new Date('2026-01-01T10:00:20Z'))
    await press()
    await vi.waitFor(async () => {
      expect(await stamp()).not.toBe(first)
    })
  } finally {
    vi.useRealTimers()
  }
})

test('a failed check shows its reason, then a pass replaces it', async () => {
  const replies = [missingScopes, pass]
  ownerWithConnection(() => slackConnection, {
    [`POST ${base}connections/slack/refresh/`]: () => replies.shift()!(),
  })
  render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  const user = userEvent.setup()
  const press = () =>
    user.click(
      within(slack).getByRole('button', { name: 'Check Slack status' }),
    )
  await press()
  const alert = await within(slack).findByRole('alert')
  expect(alert).toHaveTextContent('Slack check failed')
  expect(alert).toHaveTextContent('Grant the required Slack scopes')
  expect(within(slack).queryByText(/connection is working/)).toBeNull()
  expect(within(slack).queryByText('Connection update failed')).toBeNull()
  await press()
  expect(
    await within(slack).findByText(/Slack connection is working/),
  ).toBeVisible()
  expect(within(slack).queryByRole('alert')).toBeNull()
})

test('channel actions never read as a check result', async () => {
  const connection = {
    ...slackConnection,
    channels: [{ channel_id: 'C1', name: 'support', is_private: false }],
  }
  const replies = [pass, missingScopes]
  ownerWithConnection(() => connection, {
    [`GET ${base}channels/`]: () => json({ channels: [], truncated: false }),
    [`POST ${base}channels/`]: () => replies.shift()!(),
  })
  render()
  const slack = await screen.findByRole('region', { name: 'Slack' })
  const user = userEvent.setup()
  const remove = () =>
    user.click(
      within(slack).getByRole('button', { name: 'Remove channel support' }),
    )
  await remove()
  await vi.waitFor(() => expect(replies).toHaveLength(1))
  expect(within(slack).queryByText(/connection is working/)).toBeNull()
  await remove()
  expect(
    await within(slack).findByText('Connection update failed'),
  ).toBeVisible()
  expect(within(slack).queryByText(/check failed/)).toBeNull()
})

test('channel picker offers named channels with unavailable choices disabled', async () => {
  const connection = {
    ...slackConnection,
    channels: [
      { channel_id: 'C1', name: 'already-allowed', is_private: false },
    ],
  }
  const fetch = ownerWithConnection(() => connection, {
    [`GET ${base}channels/`]: () =>
      json({
        channels: [
          {
            channel_id: 'C1',
            name: 'already-allowed',
            is_private: false,
            unavailable_reason: '',
          },
          {
            channel_id: 'C2',
            name: 'support-requests',
            is_private: false,
            unavailable_reason: '',
          },
          {
            channel_id: 'G2',
            name: 'key-accounts',
            is_private: true,
            unavailable_reason: '',
          },
          {
            channel_id: 'C3',
            name: 'partner-shared',
            is_private: false,
            unavailable_reason: 'externally_shared',
          },
          {
            channel_id: 'C4',
            name: 'unknown-reason',
            is_private: false,
            unavailable_reason: 'future_reason',
          },
        ],
        truncated: false,
      }),
    [`POST ${base}channels/`]: () => json({}),
  })
  render()
  const select = await screen.findByLabelText('Slack channel')
  expect(
    within(select).getByRole('option', { name: '#key-accounts · Private' }),
  ).toBeInTheDocument()
  expect(
    within(select).getByRole('option', { name: '#support-requests · Public' }),
  ).toBeInTheDocument()
  expect(
    within(select).getByRole('option', {
      name: '#partner-shared · Slack Connect, not allowed',
    }),
  ).toBeDisabled()
  expect(
    within(select).getByRole('option', {
      name: '#unknown-reason · Not allowed',
    }),
  ).toBeDisabled()
  expect(
    within(select).queryByRole('option', { name: '#already-allowed · Public' }),
  ).toBeNull()
  expect(
    screen.queryByRole('textbox', { name: 'Slack channel ID' }),
  ).not.toBeInTheDocument()
  expect(
    screen
      .getByRole('heading', { name: 'Allowed Slack channels' })
      .compareDocumentPosition(
        screen.getByRole('button', { name: 'Reconnect Slack' }),
      ) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Allow channel' })).toBeDisabled()
  const user = userEvent.setup()
  const channelConsent = screen.getByRole('checkbox', {
    name: 'Reports captured from this channel will be visible to all members of Example.',
  })
  const reconnectConsent = screen.getByRole('checkbox', {
    name: 'Reports captured from approved channels will be visible to all members of Example.',
  })
  await user.click(reconnectConsent)
  expect(screen.getByRole('button', { name: 'Allow channel' })).toBeDisabled()
  await user.selectOptions(select, 'C2')
  expect(screen.getByRole('button', { name: 'Allow channel' })).toBeDisabled()
  await user.click(channelConsent)
  expect(screen.getByRole('button', { name: 'Allow channel' })).toBeEnabled()
  await user.click(
    within(screen.getByRole('region', { name: 'Slack' })).getByRole('button', {
      name: 'Allow channel',
    }),
  )
  await vi.waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith('/channels/') &&
          init?.method === 'POST' &&
          JSON.stringify(JSON.parse(String(init.body))) ===
            JSON.stringify({ version: 1, channel_id: 'C2', consent: true }),
      ),
    ).toBe(true),
  )
  await vi.waitFor(() => expect(channelConsent).not.toBeChecked())
})

test('channel picker sends the current consent checkbox value', async () => {
  const fetch = ownerWithConnection(() => slackConnection, {
    [`GET ${base}channels/`]: () =>
      json({
        channels: [
          {
            channel_id: 'C2',
            name: 'support-requests',
            is_private: false,
            unavailable_reason: '',
          },
        ],
        truncated: false,
      }),
    [`POST ${base}channels/`]: () =>
      json(
        {
          detail: 'Confirm publication before allowing a channel.',
          reason: 'consent_required',
          field_errors: {},
        },
        400,
      ),
  })
  render()
  const select = await screen.findByLabelText('Slack channel')
  await userEvent.setup().selectOptions(select, 'C2')
  fireEvent.submit(select.closest('form')!)
  await vi.waitFor(() => {
    const request = fetch.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith('/channels/') && init?.method === 'POST',
    )
    expect(request).toBeDefined()
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      version: 1,
      channel_id: 'C2',
      consent: false,
    })
  })
})

test('channel picker shows loading, rate-limit retry, empty and truncated states', async () => {
  let calls = 0
  const fetch = ownerWithConnection(() => slackConnection, {
    [`GET ${base}channels/`]: () => {
      calls += 1
      if (calls === 1)
        return json(
          {
            detail: 'Slack asked us to wait. Try again in a minute.',
            reason: 'slack_rate_limited',
            field_errors: {},
          },
          400,
        )
      if (calls === 2) return json({ channels: [], truncated: false })
      return json({
        channels: [
          {
            channel_id: 'C4',
            name: 'later',
            is_private: false,
            unavailable_reason: '',
          },
        ],
        truncated: true,
      })
    },
  })
  render()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Slack asked us to wait',
  )
  await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText(/invite it to a channel/)).toBeVisible()
  await userEvent.click(
    screen.getByRole('button', { name: 'Refresh channel list' }),
  )
  expect(
    await screen.findByText('Showing the first 1,000 channels.'),
  ).toBeVisible()
  expect(
    fetch.mock.calls.filter(([input]) => String(input).endsWith('/channels/')),
  ).toHaveLength(3)
})

test('channel picker asks for an internal channel when only Slack Connect is available', async () => {
  ownerWithConnection(() => slackConnection, {
    [`GET ${base}channels/`]: () =>
      json({
        channels: [
          {
            channel_id: 'C3',
            name: 'partner-shared',
            is_private: false,
            unavailable_reason: 'externally_shared',
          },
        ],
        truncated: false,
      }),
  })
  render()
  expect(await screen.findByText(/invite it to a channel/)).toBeVisible()
  expect(
    await screen.findByRole('option', {
      name: '#partner-shared · Slack Connect, not allowed',
    }),
  ).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Allow channel' })).toBeDisabled()
})

test('channel picker announces its loading state before Slack responds', async () => {
  ownerWithConnection(() => slackConnection, {
    [`GET ${base}channels/`]: () =>
      new Promise<Response>(() => {}) as unknown as Response,
  })
  render()
  expect(
    await screen.findByRole('status', { name: 'Loading Slack channels' }),
  ).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Allow channel' })).toBeNull()
})

test('demo workspaces never request the Slack channel list', async () => {
  testMembership.role = 'owner'
  testMembership.workspace.is_demo = true
  const fetch = stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json([slackConnection]),
    [`GET ${base}memberships/`]: () => json([]),
    [`GET ${base}invitations/`]: () => json([]),
  })
  render()
  await screen.findByRole('heading', { name: 'Slack' })
  expect(
    fetch.mock.calls.some(([input]) => String(input).endsWith('/channels/')),
  ).toBe(false)
})

test('a passed result is hidden when the connection is no longer active', async () => {
  let current: unknown = githubConnection
  ownerWithConnection(() => current, {
    [`POST ${base}connections/github/refresh/`]: () => {
      current = { ...githubConnection, status: 'error' }
      return pass()
    },
  })
  render()
  const github = await screen.findByRole('region', { name: 'GitHub' })
  await userEvent.click(
    within(github).getByRole('button', { name: 'Check GitHub status' }),
  )
  await vi.waitFor(() => expect(current).toHaveProperty('status', 'error'))
  await within(github).findByText('Needs attention')
  expect(within(github).queryByText(/connection is working/)).toBeNull()
})

test.each([
  ['slack', 'Connect Slack'],
  ['github', 'Connect GitHub'],
] as const)(
  '%s setup shows a rejected repository where the owner can see it',
  async (provider, button) => {
    testMembership.role = 'owner'
    stubApi({
      ...unlinked,
      [`GET ${base}connections/`]: () => json([]),
      [`GET ${base}memberships/`]: () => json([]),
      [`GET ${base}invitations/`]: () => json([]),
      [`POST ${base}connections/${provider}/setup/`]: () =>
        json(
          {
            detail: 'Check the submitted fields.',
            reason: 'invalid_request',
            field_errors: { repository: ['This field may not be blank.'] },
          },
          400,
        ),
    })
    render()
    const name = provider === 'slack' ? 'Slack' : 'GitHub'
    const card = await screen.findByRole('region', { name })
    const user = userEvent.setup()
    if (provider === 'github') {
      await user.type(
        within(card).getByLabelText('GitHub repository'),
        'acme/web',
      )
    }
    await user.click(within(card).getByRole('checkbox'))
    await user.click(within(card).getByRole('button', { name: button }))
    const summary = (
      await within(card).findByText(`Could not connect ${name}`)
    ).closest('[role="alert"]')
    if (provider === 'slack') {
      expect(summary).toHaveTextContent(
        'Check the submitted fields. Repository: This field may not be blank.',
      )
    } else {
      expect(summary).not.toHaveTextContent('Repository:')
      expect(
        within(card).getAllByText('This field may not be blank.'),
      ).toHaveLength(1)
    }
  },
)

// Model provider
const modelConnection = {
  ...slackConnection,
  provider: 'model',
  identity: '',
  external_id: '',
  api_style: 'anthropic',
  base_url: 'https://api.anthropic.com',
  model: 'claude-test',
  last_success_at: '2026-10-01T10:00:00Z',
}
function modelApi(
  connections: unknown[],
  extra: Record<string, (url: URL, init?: RequestInit) => Response> = {},
) {
  return stubApi({
    ...unlinked,
    [`GET ${base}connections/`]: () => json(connections),
    ...extra,
  })
}
const modelCard = () => screen.findByRole('region', { name: 'Model provider' })
const connectBodies = (fetch: ReturnType<typeof stubApi>) =>
  fetch.mock.calls
    .filter(([input]) => String(input).endsWith('connections/model/connect/'))
    .map(([, init]) => JSON.parse(String(init?.body)))

test('the model card reads not connected and asks a member to contact an owner', async () => {
  modelApi([])
  render()
  const card = await modelCard()
  expect(within(card).getByText('Not connected')).toHaveAttribute(
    'data-tone',
    'neutral',
  )
  expect(
    within(card).getByText(
      'Ask a workspace owner to connect a model provider.',
    ),
  ).toBeVisible()
  expect(within(card).queryByRole('textbox')).not.toBeInTheDocument()
  expect(within(card).queryByRole('checkbox')).not.toBeInTheDocument()
})

test('an active model card shows its values and no job counts', async () => {
  modelApi([modelConnection])
  render()
  const card = await modelCard()
  expect(within(card).getByText('Connected')).toHaveAttribute(
    'data-tone',
    'success',
  )
  expect(within(card).getByText('Anthropic')).toBeVisible()
  expect(within(card).getByText('https://api.anthropic.com')).toBeVisible()
  expect(within(card).getByText('claude-test')).toBeVisible()
  expect(
    within(card).getByText(formatDate('2026-10-01T10:00:00Z')),
  ).toBeVisible()
  expect(within(card).queryByRole('group', { name: 'Jobs' })).toBeNull()
})

test('a model connection in error shows the next step', async () => {
  testMembership.role = 'owner'
  modelApi([
    {
      ...modelConnection,
      status: 'error',
      error_code: 'model_auth_rejected',
      error_detail: 'The provider rejected the API key.',
    },
  ])
  render()
  const card = await modelCard()
  expect(within(card).getByText('Needs attention')).toBeVisible()
  expect(
    within(card).getByText('The provider rejected the API key.'),
  ).toBeVisible()
  expect(
    within(card).getByRole('button', { name: 'Check model provider status' }),
  ).toBeVisible()
})

test('picking a named provider fills its base URL, and consent gates connect', async () => {
  testMembership.role = 'owner'
  const fetch = modelApi([], {
    [`POST ${base}connections/model/connect/`]: () =>
      new Response(null, { status: 204 }),
  })
  render()
  const card = await modelCard()
  const user = userEvent.setup()
  const baseUrl = await within(card).findByLabelText('Base URL')
  expect(baseUrl).toHaveValue('https://api.openai.com/v1')
  await user.selectOptions(within(card).getByLabelText('Provider'), 'anthropic')
  expect(baseUrl).toHaveValue('https://api.anthropic.com')
  await user.type(within(card).getByLabelText('Model'), 'claude-test')
  const key = within(card).getByLabelText('API key')
  expect(key).toHaveAttribute('type', 'password')
  expect(key).toHaveAttribute('autocomplete', 'off')
  await user.type(key, 'sk-test')
  const connect = within(card).getByRole('button', {
    name: 'Connect model provider',
  })
  expect(connect).toBeDisabled()
  await user.click(within(card).getByRole('checkbox'))
  await user.click(connect)
  await vi.waitFor(() => expect(connectBodies(fetch)).toHaveLength(1))
  expect(connectBodies(fetch)[0]).toEqual({
    api_style: 'anthropic',
    base_url: 'https://api.anthropic.com',
    model: 'claude-test',
    api_key: 'sk-test',
    consent: true,
  })
})

test('a failed connection test keeps the form but clears the key', async () => {
  testMembership.role = 'owner'
  modelApi([], {
    [`POST ${base}connections/model/connect/`]: () =>
      json(
        {
          detail: 'The model did not return JSON that matches the schema.',
          reason: 'model_no_structured_output',
          field_errors: {},
        },
        400,
      ),
  })
  render()
  const card = await modelCard()
  const user = userEvent.setup()
  await user.type(await within(card).findByLabelText('Model'), 'gpt-test')
  await user.type(within(card).getByLabelText('API key'), 'sk-test')
  await user.click(within(card).getByRole('checkbox'))
  await user.click(
    within(card).getByRole('button', { name: 'Connect model provider' }),
  )
  expect(
    await within(card).findByText(/did not return JSON that matches/),
  ).toBeVisible()
  expect(within(card).getByLabelText('Model')).toHaveValue('gpt-test')
  expect(within(card).getByLabelText('Base URL')).toHaveValue(
    'https://api.openai.com/v1',
  )
  expect(within(card).getByLabelText('API key')).toHaveValue('')
})

test('a deployment-managed provider is read-only with only consent to enable', async () => {
  testMembership.role = 'owner'
  const fetch = modelApi([], {
    [`GET ${base}connections/model/deployment/`]: () =>
      json({
        managed: true,
        api_style: 'openai',
        base_url: 'http://ollama:11434/v1',
        model: 'llama3.3',
      }),
    [`POST ${base}connections/model/connect/`]: () =>
      new Response(null, { status: 204 }),
  })
  render()
  const card = await modelCard()
  expect(
    await within(card).findByText(/This deployment sets the model provider/),
  ).toBeVisible()
  expect(within(card).getByText('http://ollama:11434/v1')).toBeVisible()
  expect(within(card).getByText('llama3.3')).toBeVisible()
  expect(within(card).queryByLabelText('Base URL')).toBeNull()
  expect(within(card).queryByLabelText('API key')).toBeNull()
  expect(within(card).queryByLabelText('Provider')).toBeNull()
  const enable = within(card).getByRole('button', {
    name: 'Enable model provider',
  })
  expect(enable).toBeDisabled()
  await userEvent.click(within(card).getByRole('checkbox'))
  await userEvent.click(enable)
  await vi.waitFor(() =>
    expect(connectBodies(fetch)).toEqual([{ consent: true }]),
  )
})
