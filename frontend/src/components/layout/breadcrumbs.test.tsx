import { render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { getProblem, problemKeys } from '@/api/problems'
import { useQuery } from '@tanstack/react-query'
import { Breadcrumbs } from './breadcrumbs'

const membership = {
  membership_id: 'm-1',
  role: 'owner' as const,
  workspace: {
    id: 'ws-1',
    name: 'Workspace',
    slug: 'workspace',
    is_demo: false,
  },
}

test.each([
  ['/inbox', 'Inbox'],
  ['/inbox/new', 'New report'],
  ['/problems', 'Problems'],
  ['/follow-ups', 'Follow-ups'],
  ['/settings', 'Settings'],
  ['/dev/ui', 'UI gallery'],
])('shows the current section for %s', (path, label) => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Breadcrumbs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(
    screen.getByRole('navigation', { name: 'Breadcrumb' }),
  ).toBeInTheDocument()
  expect(screen.getByText(label)).toHaveAttribute('aria-current', 'page')
})

test('the new report breadcrumb links to Inbox', () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/inbox/new']}>
        <Breadcrumbs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(screen.getByRole('link', { name: 'Inbox' })).toHaveAttribute(
    'href',
    '/inbox',
  )
  expect(screen.getByText('New report')).toHaveAttribute('aria-current', 'page')
})

test.each([
  ['/inbox/report-1', 'Inbox'],
  ['/problems/problem-1', 'Problem'],
  ['/follow-ups/follow-up-1', 'Follow-ups'],
  ['/follow-ups/follow-up-1/page', 'Follow-up'],
])('renders the expected fallback trail for %s', (path, label) => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Breadcrumbs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(screen.getByText(label)).toBeInTheDocument()
  if (path === '/problems/problem-1' || path.endsWith('/page')) {
    expect(
      screen.getByRole('link', {
        name: path.startsWith('/problems') ? 'Problems' : 'Follow-ups',
      }),
    ).toBeInTheDocument()
  }
})

test('shows the follow-up page report title and links to its section', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({ report: { title: 'Reset email delay' } }),
          {
            status: 200,
          },
        ),
    ),
  )
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <WorkspaceProvider membership={membership}>
        <MemoryRouter initialEntries={['/follow-ups/follow-up-1/page']}>
          <Breadcrumbs />
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
  const breadcrumb = screen.getByRole('navigation', { name: 'Breadcrumb' })
  expect(await screen.findByText('Reset email delay')).toHaveAttribute(
    'aria-current',
    'page',
  )
  expect(
    within(breadcrumb).getByRole('link', { name: 'Follow-ups' }),
  ).toHaveAttribute('href', '/follow-ups')
})

test('uses the fallback title when the detail request fails', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('failed', { status: 500 })),
  )
  render(
    <QueryClientProvider client={client}>
      <WorkspaceProvider membership={membership}>
        <MemoryRouter initialEntries={['/problems/problem-1']}>
          <Breadcrumbs />
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
  await waitFor(() =>
    expect(
      client.getQueryState(problemKeys.detail('ws-1', 'problem-1'))?.status,
    ).toBe('error'),
  )
  await waitFor(() =>
    expect(screen.getByText('Problem')).toHaveAttribute('aria-current', 'page'),
  )
})

test('shares the problem detail query with the page', async () => {
  const fetcher = vi.fn(
    async () =>
      new Response(JSON.stringify({ title: 'Late reset link' }), {
        status: 200,
      }),
  )
  vi.stubGlobal('fetch', fetcher)
  function ProblemPageQuery() {
    useQuery({
      queryKey: problemKeys.detail('ws-1', 'problem-1'),
      queryFn: () => getProblem('ws-1', 'problem-1'),
    })
    return null
  }
  render(
    <QueryClientProvider client={new QueryClient()}>
      <WorkspaceProvider membership={membership}>
        <MemoryRouter initialEntries={['/problems/problem-1']}>
          <ProblemPageQuery />
          <Breadcrumbs />
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
  expect(await screen.findByText('Late reset link')).toBeInTheDocument()
  expect(fetcher).toHaveBeenCalledTimes(1)
})
