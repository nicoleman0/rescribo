import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import { sessionQueryKey, type Session } from '@/api/auth'
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
  const shell = (
    <QueryClientProvider client={client}>
      {withWorkspace ? (
        <WorkspaceProvider membership={demo}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route element={<AppShell />}>
                <Route path="*" element={<h1>Page</h1>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </WorkspaceProvider>
      ) : (
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="*" element={<h1>Page</h1>} />
            </Route>
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
  for (const name of ['Inbox', 'Problems', 'Follow-ups', 'Settings']) {
    expect(screen.getAllByRole('link', { name }).length).toBeGreaterThan(0)
  }
  const skip = screen.getByRole('link', { name: 'Skip to main content' })
  expect(document.body.querySelectorAll('a[href], button')[0]).toBe(skip)
  expect(document.getElementById('main-content')).toHaveAttribute(
    'tabindex',
    '-1',
  )
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

test('wordmark links to Inbox when expanded', () => {
  renderShell('/settings')
  fireEvent.click(screen.getByRole('link', { name: 'rescribo, go to inbox' }))
  expect(screen.getByRole('heading', { name: 'Page' })).toBeInTheDocument()
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
