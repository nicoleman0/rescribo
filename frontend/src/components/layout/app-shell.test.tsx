import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import { sessionQueryKey, type Session } from '@/api/auth'
import { reportKeys } from '@/api/reports'
import { followUpKeys } from '@/api/follow-ups'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { AppShell } from './app-shell'

const session: Session = {
  user: { id: 'u-1', full_name: 'Ada Lovelace', email: 'ada@example.test' },
  memberships: [],
}
const demo = {
  membership_id: 'm-1',
  role: 'member' as const,
  workspace: {
    id: 'ws-1',
    name: 'Northwind (demo)',
    slug: 'demo',
    is_demo: true,
  },
}

function renderShell(path = '/inbox', withWorkspace = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(sessionQueryKey, session)
  function PageHeading() {
    const { pathname } = useLocation()
    return <h1>{pathname === '/inbox' ? 'Inbox page' : 'Settings page'}</h1>
  }
  const shell = (
    <QueryClientProvider client={client}>
      {withWorkspace ? (
        <WorkspaceProvider membership={demo}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route element={<AppShell />}>
                <Route path="*" element={<PageHeading />} />
              </Route>
              <Route path="/sign-in" element={<h1>Sign in</h1>} />
            </Routes>
          </MemoryRouter>
        </WorkspaceProvider>
      ) : (
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="*" element={<PageHeading />} />
            </Route>
            <Route path="/sign-in" element={<h1>Sign in</h1>} />
          </Routes>
        </MemoryRouter>
      )}
    </QueryClientProvider>
  )
  return { ...render(shell), client }
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query.includes('max-width') ? false : false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
})

test('shows all exact navigation names and keeps the skip link first', () => {
  renderShell()
  expect(document.querySelector('[data-slot="sidebar-menu"]')).toHaveClass(
    'gap-[3px]',
  )
  for (const name of ['Inbox', 'Problems', 'Follow-ups', 'Settings']) {
    expect(screen.getAllByRole('link', { name }).length).toBeGreaterThan(0)
  }
  const skip = screen.getByRole('link', { name: 'Skip to main content' })
  expect(document.body.querySelectorAll('a[href], button')[0]).toBe(skip)
  expect(document.getElementById('main-content')).toHaveAttribute(
    'tabindex',
    '-1',
  )
  expect(
    document.querySelector('[data-slot="sidebar-menu-button"][href="/inbox"]'),
  ).toHaveAttribute('data-active', 'true')
})

test('the user menu holds sign out and the UI gallery has no menu', async () => {
  const user = userEvent.setup()
  renderShell()
  expect(
    screen.queryByRole('button', { name: 'Sign out' }),
  ).not.toBeInTheDocument()
  const trigger = screen.getAllByRole('button', {
    name: /User menu for Ada Lovelace/,
  })[0]
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(trigger).toHaveAttribute('aria-expanded', 'true')
  expect(
    await screen.findByRole('menuitem', { name: 'Sign out' }),
  ).toBeInTheDocument()
})

test('the user menu shows the version from the API', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const body = String(input).includes('/api/version/')
        ? { version: '0.1.0' }
        : session
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
  const user = userEvent.setup()
  renderShell('/inbox', true)
  screen
    .getAllByRole('button', { name: /User menu for Ada Lovelace/ })[0]
    .focus()
  await user.keyboard('{Enter}')
  expect(await screen.findByText('Rescribo 0.1.0')).toBeInTheDocument()
})

test('a failed version request leaves the menu working without a version line', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes('/api/version/')
        ? new Response('failed', { status: 500 })
        : new Response(JSON.stringify(session), { status: 200 }),
    ),
  )
  const user = userEvent.setup()
  renderShell('/inbox', true)
  screen
    .getAllByRole('button', { name: /User menu for Ada Lovelace/ })[0]
    .focus()
  await user.keyboard('{Enter}')
  await screen.findByRole('menuitem', { name: 'Sign out' })
  await waitFor(() =>
    expect(screen.queryByText(/Rescribo 0\./)).not.toBeInTheDocument(),
  )
  expect(screen.getByRole('menuitem', { name: 'Sign out' })).toBeInTheDocument()
})

test('sign out calls logout and navigates to sign in', async () => {
  const user = userEvent.setup()
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).includes('/auth/logout/')) {
      return new Response(null, { status: 204 })
    }
    return new Response(JSON.stringify(session), { status: 200 })
  })
  vi.stubGlobal('fetch', fetcher)
  renderShell()
  const trigger = screen.getAllByRole('button', {
    name: /User menu for Ada Lovelace/,
  })[0]
  trigger.focus()
  await user.keyboard('{Enter}')
  await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
  await waitFor(() =>
    expect(
      screen.getByRole('heading', { name: 'Sign in' }),
    ).toBeInTheDocument(),
  )
  expect(fetcher).toHaveBeenCalledWith(
    '/api/auth/logout/',
    expect.objectContaining({ method: 'POST' }),
  )
})

test('failed sign out exposes an alert', async () => {
  const user = userEvent.setup()
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) =>
      String(input).includes('/auth/logout/')
        ? new Response(JSON.stringify({ detail: 'Logout failed.' }), {
            status: 500,
          })
        : new Response(JSON.stringify(session), { status: 200 }),
    ),
  )
  renderShell()
  screen
    .getAllByRole('button', { name: /User menu for Ada Lovelace/ })[0]
    .focus()
  await user.keyboard('{Enter}')
  await user.click(await screen.findByRole('menuitem', { name: 'Sign out' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Logout failed.')
})

test('the gallery shows no user menu or Sign out', () => {
  renderShell('/dev/ui')
  expect(
    screen.queryByRole('button', { name: /User menu for/ }),
  ).not.toBeInTheDocument()
  expect(
    screen.queryByRole('menuitem', { name: 'Sign out' }),
  ).not.toBeInTheDocument()
})

test('demo sentence is inside the user menu', async () => {
  const user = userEvent.setup()
  renderShell('/follow-ups', true)
  expect(screen.getByLabelText('Demo workspace')).toHaveTextContent('Demo')
  expect(
    screen.queryByText('Fictitious data. Nothing is sent to Slack or GitHub.'),
  ).not.toBeInTheDocument()
  const trigger = screen.getAllByRole('button', {
    name: /User menu for Ada Lovelace/,
  })[0]
  trigger.focus()
  await user.keyboard('{Enter}')
  expect(
    await screen.findByText(
      'Fictitious data. Nothing is sent to Slack or GitHub.',
    ),
  ).toBeInTheDocument()
})

test('does not show the Demo badge outside a demo workspace', () => {
  renderShell('/inbox')
  expect(screen.queryByLabelText('Demo workspace')).not.toBeInTheDocument()
})

test('wordmark links to Inbox when expanded', () => {
  renderShell('/settings')
  fireEvent.click(screen.getByRole('link', { name: 'rescribo, go to inbox' }))
  expect(
    screen.getByRole('heading', { name: 'Inbox page' }),
  ).toBeInTheDocument()
})

test('collapsing hides the wordmark and stores the rail preference', async () => {
  const user = userEvent.setup()
  renderShell('/settings')
  await user.click(screen.getByRole('button', { name: 'Toggle Sidebar' }))
  expect(
    screen.queryByRole('link', { name: 'rescribo, go to inbox' }),
  ).not.toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: 'Inbox' }).length).toBeGreaterThan(
    0,
  )
  expect(localStorage.getItem('rescribo-sidebar')).toBe('false')
})

test('shows navigation counts with accessible labels and keeps link names exact', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const body = url.includes('/auth/session/')
        ? session
        : { count: url.includes('/reports/') ? 3 : 2, results: [] }
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
  renderShell('/inbox', true)
  await waitFor(() =>
    expect(screen.getAllByText('3 new reports').length).toBeGreaterThan(0),
  )
  expect(
    screen.getAllByText('2 follow-ups need approval').length,
  ).toBeGreaterThan(0)
  expect(screen.getAllByRole('link', { name: 'Inbox' }).length).toBeGreaterThan(
    0,
  )
  expect(
    screen.getAllByRole('link', { name: 'Follow-ups' }).length,
  ).toBeGreaterThan(0)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

test.each([
  ['zero', 0, '0'],
  ['large', 120, '99+'],
])('renders the %s report count correctly', async (_name, count, label) => {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const body = url.includes('/auth/session/')
      ? session
      : { count: url.includes('/reports/') ? count : 0, results: [] }
    return new Response(JSON.stringify(body), { status: 200 })
  })
  vi.stubGlobal('fetch', fetcher)
  const { client } = renderShell('/inbox', true)
  if (count === 0) {
    await waitFor(() => {
      expect(
        client.getQueryData(reportKeys.list('ws-1', { triage_state: 'new' })),
      ).toEqual({ count: 0, results: [] })
      expect(
        client.getQueryData(followUpKeys.list('ws-1', 'needs_approval', 1)),
      ).toEqual({ count: 0, results: [] })
    })
    expect(
      document.querySelectorAll('[data-slot="sidebar-menu-badge"]'),
    ).toHaveLength(0)
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  } else {
    await waitFor(() =>
      expect(screen.getAllByText(label).length).toBeGreaterThan(0),
    )
    expect(screen.getAllByText('120 new reports')).toHaveLength(2)
  }
})

test('does not show count badges when the count request fails', async () => {
  const fetcher = vi.fn(async () => new Response('failed', { status: 500 }))
  vi.stubGlobal('fetch', fetcher)
  renderShell('/inbox', true)
  // Three count attempts plus the non-retrying version request.
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(4))
  expect(
    document.querySelectorAll('[data-slot="sidebar-menu-badge"]'),
  ).toHaveLength(0)
})

test('does not show count badges while count requests are pending', () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise<Response>(() => undefined)),
  )
  const view = renderShell('/inbox', true)
  expect(
    document.querySelectorAll('[data-slot="sidebar-menu-badge"]'),
  ).toHaveLength(0)
  expect(screen.queryByText(/new reports/)).not.toBeInTheDocument()
  view.unmount()
  view.client.clear()
})

test('Ctrl+B collapses the sidebar and stores the rail preference', () => {
  renderShell('/settings')
  fireEvent.keyDown(window, { key: 'b', ctrlKey: true })
  expect(
    screen.queryByRole('link', { name: 'rescribo, go to inbox' }),
  ).not.toBeInTheDocument()
  expect(localStorage.getItem('rescribo-sidebar')).toBe('false')
})

test('the palette trigger is absent from the UI gallery and without a workspace', () => {
  renderShell('/dev/ui')
  expect(
    screen.queryByRole('button', { name: 'Open command palette' }),
  ).not.toBeInTheDocument()
})
