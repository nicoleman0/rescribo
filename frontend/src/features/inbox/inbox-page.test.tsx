import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ReportDetail, ReportListItem, ReportPage } from '@/api/reports'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { InboxPage } from './inbox-page'

const member = {
  id: 'mem-2',
  full_name: 'Ada Lovelace',
  email: 'ada@example.test',
}

const listItem: ReportListItem = {
  id: 'rep-1',
  title: 'CSV export fails',
  customer_label: 'Acme',
  triage_state: 'new',
  source_kind: 'slack',
  assignee: member,
  problem: null,
  created_at: '2026-09-20T10:00:00Z',
}

const page = (results: ReportListItem[], extra: Partial<ReportPage> = {}) =>
  json({ count: results.length, next: null, previous: null, results, ...extra })

const routes = [
  { path: '/inbox', element: <InboxPage /> },
  { path: '/inbox/:reportId', element: <InboxPage /> },
]

const reportsPath = 'GET /api/workspaces/ws-1/reports/'
const membersPath = 'GET /api/workspaces/ws-1/members/'

test('lists reports and sends search and filter changes to the API', async () => {
  const queries: string[] = []
  stubApi({
    [reportsPath]: (url) => {
      queries.push(url.search)
      return page([listItem])
    },
    [membersPath]: () => json([member]),
  })
  renderWorkspaceRoutes(routes, '/inbox')
  const list = await screen.findByRole('list', { name: 'Reports' })
  expect(
    within(list).getByRole('link', { name: /CSV export fails/ }),
  ).toHaveAttribute('href', '/inbox/rep-1')
  expect(within(list).getByText('Ada Lovelace')).toBeInTheDocument()
  expect(screen.getByText('1 report')).toBeInTheDocument()

  fireEvent.change(screen.getByRole('searchbox', { name: 'Search reports' }), {
    target: { value: ' export ' },
  })
  fireEvent.change(screen.getByRole('searchbox', { name: 'Customer' }), {
    target: { value: 'acme' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
  await waitFor(() => expect(queries.at(-1)).toBe('?q=export&customer=acme'))

  fireEvent.change(screen.getByRole('combobox', { name: 'Status' }), {
    target: { value: 'linked' },
  })
  await waitFor(() => expect(queries.at(-1)).toContain('triage_state=linked'))
  await screen.findByRole('option', { name: 'Ada Lovelace' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Assignee' }), {
    target: { value: 'mem-2' },
  })
  await waitFor(() => expect(queries.at(-1)).toContain('assignee=mem-2'))
  fireEvent.change(screen.getByRole('combobox', { name: 'Source' }), {
    target: { value: 'manual' },
  })
  await waitFor(() => expect(queries.at(-1)).toContain('source_kind=manual'))
  expect(screen.getByTestId('location')).toHaveTextContent(
    '/inbox?q=export&customer=acme&triage_state=linked&assignee=mem-2&source_kind=manual',
  )

  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  await waitFor(() => expect(queries.at(-1)).toBe(''))
  expect(screen.getByRole('searchbox', { name: 'Search reports' })).toHaveValue(
    '',
  )
})

test('pages through results and keeps the filters', async () => {
  const queries: string[] = []
  stubApi({
    [reportsPath]: (url) => {
      queries.push(url.search)
      return url.searchParams.get('page') === '2'
        ? page([{ ...listItem, id: 'rep-2', title: 'Second page' }], {
            count: 26,
            previous: 'http://testserver/?q=x',
          })
        : page([listItem], { count: 26, next: 'http://testserver/?page=2' })
    },
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?q=x')
  await screen.findByText('26 reports · page 1')
  expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  await screen.findByText('Second page')
  expect(queries.at(-1)).toBe('?q=x&page=2')
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled()
})

test('distinguishes an empty inbox from an empty filtered result', async () => {
  stubApi({ [reportsPath]: () => page([]), [membersPath]: () => json([]) })
  const view = renderWorkspaceRoutes(routes, '/inbox')
  expect(await screen.findByText('No reports yet')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'New report' })).toHaveAttribute(
    'href',
    '/inbox/new',
  )
  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox?source_kind=slack')
  expect(
    await screen.findByText('No reports match these filters'),
  ).toBeInTheDocument()
})

test('shows an error with retry that keeps the filters', async () => {
  let calls = 0
  stubApi({
    [reportsPath]: () => {
      calls += 1
      return calls === 1
        ? json({ detail: 'Server error', reason: 'error' }, 500)
        : page([listItem])
    },
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?customer=acme')
  expect(await screen.findByText('Could not load reports')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('CSV export fails')).toBeInTheDocument()
  expect(screen.getByRole('searchbox', { name: 'Customer' })).toHaveValue(
    'acme',
  )
})

test('explains invalid filters from the URL', async () => {
  stubApi({
    [reportsPath]: () =>
      json(
        { detail: 'Check the submitted fields.', reason: 'invalid_request' },
        400,
      ),
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?assignee=nobody')
  expect(
    await screen.findByText('These filters are not valid'),
  ).toBeInTheDocument()
})

const detail: ReportDetail = {
  ...listItem,
  description: 'Export stops halfway.',
  customer_contact_reference: 'CRM-42',
  affected_version: '2.3.1',
  provenance: {
    kind: 'slack',
    permalink: 'https://example.slack.com/archives/C1/p1',
    author_display_name: 'Grace',
    snapshot_text: 'Customer says export is broken',
    captured_at: '2026-09-20T10:00:00Z',
  },
  submitted_by: { id: 'mem-1', full_name: '', email: 'sub@example.test' },
  problem: { id: 'prob-1', title: 'Exports time out', state: 'open' },
  triage_state: 'linked',
  version: 3,
  updated_at: '2026-09-20T10:00:00Z',
}

test('shows report detail with provenance, people, and problem', async () => {
  stubApi({
    [reportsPath]: () => page([listItem]),
    [membersPath]: () => json([]),
    'GET /api/workspaces/ws-1/reports/rep-1/': () => json(detail),
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1?q=csv')
  const panel = await screen.findByRole('region', { name: 'Report detail' })
  await within(panel).findByText('Export stops halfway.')
  expect(within(panel).getByText('CRM-42')).toBeInTheDocument()
  expect(within(panel).getByText('Exports time out')).toBeInTheDocument()
  expect(within(panel).getByText('sub@example.test')).toBeInTheDocument()
  expect(within(panel).getByText('Ada Lovelace')).toBeInTheDocument()
  const source = within(panel).getByRole('region', { name: 'Provenance' })
  expect(source).toHaveTextContent('Slack message by Grace')
  expect(source).toHaveTextContent('this is not a live copy')
  expect(
    within(source).getByText('Customer says export is broken'),
  ).toBeInTheDocument()
  expect(
    within(source).getByRole('link', { name: /Open original message/ }),
  ).toHaveAttribute('href', detail.provenance.permalink)
  expect(
    within(panel).getByRole('link', { name: 'Back to reports' }),
  ).toHaveAttribute('href', '/inbox?q=csv')
  expect(
    screen.getByRole('link', { name: /CSV export fails/ }),
  ).toHaveAttribute('aria-current', 'page')
})

test('shows manual provenance and a missing report', async () => {
  stubApi({
    [reportsPath]: () => page([]),
    [membersPath]: () => json([]),
    'GET /api/workspaces/ws-1/reports/rep-1/': () =>
      json({
        ...detail,
        provenance: { ...detail.provenance, kind: 'manual', permalink: '' },
      }),
    'GET /api/workspaces/ws-1/reports/gone/': () =>
      json({ detail: 'Not found.', reason: 'not_found' }, 404),
  })
  const view = renderWorkspaceRoutes(routes, '/inbox/rep-1')
  expect(
    await screen.findByText(/Manual entry by sub@example.test/),
  ).toBeInTheDocument()
  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox/gone')
  expect(await screen.findByText('Report not found')).toBeInTheDocument()
})
