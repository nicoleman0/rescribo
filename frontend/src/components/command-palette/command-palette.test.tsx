import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { sessionQueryKey, type Session } from '@/api/auth'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { AppShell } from '@/components/layout/app-shell'
import { LocationProbe } from '@/test/location-probe'

const session: Session = {
  user: { id: 'u-1', full_name: 'Ada Lovelace', email: 'ada@example.test' },
  memberships: [],
}
const membership = {
  membership_id: 'm-1',
  role: 'member' as const,
  workspace: { id: 'ws-1', name: 'Northwind', slug: 'nw', is_demo: false },
}

type Served = {
  reports?: { id: string; title: string; customer_label: string }[]
  problems?: { id: string; title: string }[]
  /** Fail the next N report searches. */
  failReports?: number
}

function serve(served: Served = {}) {
  const searches: string[] = []
  let failReports = served.failReports ?? 0
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const page = (results: unknown[]) =>
      new Response(
        JSON.stringify({
          count: results.length,
          next: null,
          previous: null,
          results,
        }),
        { status: 200 },
      )
    if (url.includes('/auth/session/')) {
      return new Response(JSON.stringify(session), { status: 200 })
    }
    if (url.includes('q=')) searches.push(url)
    if (url.includes('/reports/') && url.includes('q=')) {
      if (failReports > 0) {
        failReports -= 1
        return new Response('{}', { status: 500 })
      }
      return page(served.reports ?? [])
    }
    if (url.includes('/problems/') && url.includes('q=')) {
      return page(served.problems ?? [])
    }
    return page([])
  })
  vi.stubGlobal('fetch', fetcher)
  return { searches }
}

function renderPalette(path = '/inbox') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  client.setQueryData(sessionQueryKey, session)
  render(
    <QueryClientProvider client={client}>
      <WorkspaceProvider membership={membership}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<AppShell />}>
              <Route
                path="*"
                element={
                  <>
                    <input aria-label="Inbox search" defaultValue="keep" />
                    <LocationProbe />
                  </>
                }
              />
            </Route>
          </Routes>
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
}

const dialog = () => screen.findByRole('dialog', { name: 'Command palette' })
const location = () => screen.getByTestId('location').textContent

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  window.innerWidth = 1280
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
  Element.prototype.scrollIntoView = () => {}
  vi.spyOn(navigator, 'platform', 'get').mockReturnValue('Win32')
})

afterEach(() => vi.restoreAllMocks())

test('opens from the trigger and from Ctrl+K, including inside a text field', async () => {
  const user = userEvent.setup()
  serve()
  renderPalette()
  const trigger = screen.getByRole('button', { name: 'Open command palette' })
  expect(trigger).toHaveAttribute('aria-keyshortcuts', 'Meta+K Control+K')

  await user.click(trigger)
  const input = within(await dialog()).getByRole('combobox')
  expect(input).toHaveFocus()
  await user.keyboard('{Escape}')
  await waitFor(() => expect(trigger).toHaveFocus())
  expect(location()).toBe('/inbox')

  const field = screen.getByRole('textbox', { name: 'Inbox search' })
  await user.click(field)
  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('{Control>}k{/Control}')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
  expect(field).toHaveValue('keep')
})

test('lists the five screens and goes to one', async () => {
  const user = userEvent.setup()
  serve()
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  const list = within(await dialog())
  for (const name of [
    'Inbox',
    'Problems',
    'Follow-ups',
    'Settings',
    'New report',
  ]) {
    expect(list.getByRole('option', { name })).toBeInTheDocument()
  }
  await user.keyboard('prob{Enter}')
  expect(location()).toBe('/problems')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
})

test('one character makes no search; two search both lists in the workspace', async () => {
  const user = userEvent.setup()
  const { searches } = serve({ reports: [], problems: [] })
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('c')
  await new Promise((resolve) => setTimeout(resolve, 300))
  expect(searches).toEqual([])
  await user.keyboard('r')
  await waitFor(() => expect(searches).toHaveLength(2))
  expect(searches.every((url) => url.startsWith('/api/workspaces/ws-1/'))).toBe(
    true,
  )
  expect(searches.some((url) => url.includes('/reports/?q=cr'))).toBe(true)
  expect(searches.some((url) => url.includes('/problems/?q=cr'))).toBe(true)
  expect(await screen.findByText('No results')).toBeInTheDocument()
})

test('shows at most five rows per group and opens a report or a problem', async () => {
  const user = userEvent.setup()
  serve({
    reports: Array.from({ length: 7 }, (_, i) => ({
      id: `r-${i}`,
      title: `Login report ${i}`,
      customer_label: 'Acme',
    })),
    problems: [{ id: 'p-1', title: 'Login loop' }],
  })
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('login')
  const reports = await screen.findAllByRole('option', {
    name: /Login report/,
  })
  expect(reports).toHaveLength(5)
  await user.click(screen.getByRole('option', { name: /Login loop/ }))
  expect(location()).toBe('/problems/p-1')

  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('login')
  await user.click(
    await screen.findByRole('option', { name: /Login report 2/ }),
  )
  expect(location()).toBe('/inbox/r-2')
})

test('says searching while a search is pending', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', (input: RequestInfo | URL) =>
    String(input).includes('/auth/session/')
      ? Promise.resolve(new Response(JSON.stringify(session)))
      : new Promise<Response>(() => undefined),
  )
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('slow')
  expect((await screen.findAllByText('Searching…')).length).toBe(2)
})

test('a failed report search offers a retry and repeats only that search', async () => {
  const user = userEvent.setup()
  const { searches } = serve({
    failReports: 1,
    reports: [{ id: 'r-1', title: 'Late report', customer_label: '' }],
    problems: [{ id: 'p-1', title: 'Late problem' }],
  })
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  await dialog()
  await user.keyboard('late')
  const retry = await screen.findByRole('option', {
    name: 'Reports could not be searched. Retry',
  })
  expect(screen.getByRole('option', { name: 'Late problem' })).toBeVisible()
  expect(searches).toHaveLength(2)

  await user.click(retry)
  expect(
    await screen.findByRole('option', { name: 'Late report' }),
  ).toBeVisible()
  expect(searches).toHaveLength(3)
  expect(searches[2]).toContain('/reports/')
  expect(screen.getByRole('dialog')).toBeInTheDocument()
})

test('changes the theme and marks the current choice', async () => {
  const user = userEvent.setup()
  serve()
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  const first = within(await dialog())
  expect(first.getAllByRole('option', { name: /theme/ })).toHaveLength(3)
  await user.click(first.getByRole('option', { name: 'Dark theme' }))
  expect(document.documentElement.dataset.theme).toBe('dark')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )

  await user.keyboard('{Control>}k{/Control}')
  expect(
    within(await dialog()).getByRole('option', { name: 'Dark theme, current' }),
  ).toBeInTheDocument()
})

test('lists shortcuts with their keys and runs one', async () => {
  const user = userEvent.setup()
  serve()
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  const list = within(await dialog())
  expect(
    list.getByRole('option', { name: 'Toggle sidebar Ctrl B' }),
  ).toBeInTheDocument()
  expect(
    list.getByRole('option', { name: 'Open command palette Ctrl K' }),
  ).toBeInTheDocument()
  await user.click(list.getByRole('option', { name: /Toggle sidebar/ }))
  expect(localStorage.getItem('rescribo-sidebar')).toBe('false')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
})

test('choosing the palette shortcut closes the palette', async () => {
  const user = userEvent.setup()
  serve()
  renderPalette()
  await user.keyboard('{Control>}k{/Control}')
  await user.click(
    within(await dialog()).getByRole('option', {
      name: /Open command palette/,
    }),
  )
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
})

test('lists no shortcuts at phone width', async () => {
  const user = userEvent.setup()
  serve()
  window.innerWidth = 390
  renderPalette()
  await user.click(screen.getByRole('button', { name: 'Open command palette' }))
  const list = within(await dialog())
  expect(list.getByRole('option', { name: 'Inbox' })).toBeInTheDocument()
  expect(list.queryByText('Shortcuts')).not.toBeInTheDocument()
  expect(list.queryByText('Toggle sidebar')).not.toBeInTheDocument()
})
