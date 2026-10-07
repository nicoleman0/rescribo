import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test } from 'vitest'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { AppShell } from './app-shell'

test('exposes all primary destinations and a keyboard skip link', () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/inbox']}>
        <AppShell>
          <h1>Inbox</h1>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  )

  expect(screen.getAllByRole('link', { name: 'Inbox' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Problems' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Follow-ups' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Settings' })).toHaveLength(2)
  expect(
    screen.getByRole('link', { name: 'Skip to main content' }),
  ).toHaveAttribute('href', '#main-content')
  expect(screen.getByRole('main')).toHaveAttribute('tabindex', '-1')
})

test('labels a demo workspace on every screen', () => {
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
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <WorkspaceProvider membership={demo}>
        <MemoryRouter initialEntries={['/follow-ups']}>
          <AppShell>
            <h1>Follow-ups</h1>
          </AppShell>
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
  expect(screen.getByLabelText('Demo workspace')).toHaveTextContent('Demo')
  expect(
    screen.getByText('Fictitious data. Nothing is sent to Slack or GitHub.'),
  ).toBeInTheDocument()

  view.rerender(
    <QueryClientProvider client={new QueryClient()}>
      <WorkspaceProvider
        membership={{
          ...demo,
          workspace: { ...demo.workspace, is_demo: false },
        }}
      >
        <MemoryRouter initialEntries={['/follow-ups']}>
          <AppShell>
            <h1>Follow-ups</h1>
          </AppShell>
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
  expect(screen.queryByLabelText('Demo workspace')).not.toBeInTheDocument()
})

test('links the sidebar wordmark to the inbox', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="settings" element={<h1>Settings</h1>} />
            <Route path="inbox" element={<h1>Inbox</h1>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  fireEvent.click(screen.getByRole('link', { name: 'rescribo, go to inbox' }))
  expect(
    await screen.findByRole('heading', { name: 'Inbox' }),
  ).toBeInTheDocument()
})
