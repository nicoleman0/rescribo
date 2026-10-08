import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ReportDetail, ReportListItem, ReportPage } from '@/api/reports'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { InboxPage } from './inbox-page'

const member = {
  id: 'mem-2',
  display_name: 'Ada Lovelace',
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
  match_state: null,
}

const page = (results: ReportListItem[], extra: Partial<ReportPage> = {}) =>
  json({ count: results.length, next: null, previous: null, results, ...extra })

const routes = [
  { path: '/inbox', element: <InboxPage /> },
  { path: '/inbox/:reportId', element: <InboxPage /> },
]

const reportsPath = 'GET /api/workspaces/ws-1/reports/'
const membersPath = 'GET /api/workspaces/ws-1/members/'

// The list and each status chip share the reports endpoint; the visible list
// is the request without a chip-only triage state.
const listQueries = (queries: string[], triageState = '') =>
  queries.filter(
    (query) =>
      new URLSearchParams(query).get('triage_state') === (triageState || null),
  )

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
  const row = within(list).getByRole('link', { name: /CSV export fails/ })
  expect(row).toHaveAttribute('href', '/inbox/rep-1')
  expect(row).toHaveTextContent(/^New.*CSV export fails/)
  expect(within(row).getByText('Assigned to Ada Lovelace')).toBeInTheDocument()
  expect(screen.getByText('1 report')).toBeInTheDocument()

  fireEvent.change(screen.getByRole('searchbox', { name: 'Search reports' }), {
    target: { value: ' export ' },
  })
  fireEvent.change(screen.getByRole('searchbox', { name: 'Customer' }), {
    target: { value: 'acme' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
  await waitFor(() =>
    expect(listQueries(queries).at(-1)).toBe('?q=export&customer=acme'),
  )

  const status = screen.getByRole('group', { name: 'Status' })
  fireEvent.click(within(status).getByRole('button', { name: /^Linked/ }))
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent(
      'triage_state=linked',
    ),
  )
  expect(
    within(status).getByRole('button', { name: /^Linked/ }),
  ).toHaveAttribute('aria-pressed', 'true')
  await screen.findByRole('option', { name: 'Ada Lovelace' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Assignee' }), {
    target: { value: 'mem-2' },
  })
  await waitFor(() =>
    expect(listQueries(queries, 'linked').at(-1)).toContain('assignee=mem-2'),
  )
  fireEvent.change(screen.getByRole('combobox', { name: 'Source' }), {
    target: { value: 'manual' },
  })
  await waitFor(() =>
    expect(listQueries(queries, 'linked').at(-1)).toContain(
      'source_kind=manual',
    ),
  )
  expect(screen.getByTestId('location')).toHaveTextContent(
    '/inbox?q=export&customer=acme&triage_state=linked&assignee=mem-2&source_kind=manual',
  )

  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  await waitFor(() => expect(listQueries(queries).at(-1)).toBe(''))
  expect(screen.getByRole('searchbox', { name: 'Search reports' })).toHaveValue(
    '',
  )
})

test('status chips count reports that match the other filters', async () => {
  const counts: Record<string, number> = { new: 2, linked: 5, dismissed: 1 }
  const queries: string[] = []
  stubApi({
    [reportsPath]: (url) => {
      queries.push(url.search)
      const state = url.searchParams.get('triage_state')
      if (state === 'dismissed') {
        return json({ detail: 'Server error', reason: 'error' }, 500)
      }
      return page([listItem], { count: state ? counts[state] : 8 })
    },
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?customer=acme')
  const status = await screen.findByRole('group', { name: 'Status' })
  expect(
    await within(status).findByRole('button', { name: 'All, 8' }),
  ).toHaveAttribute('aria-pressed', 'true')
  expect(
    await within(status).findByRole('button', { name: 'New, 2' }),
  ).toBeInTheDocument()
  expect(
    await within(status).findByRole('button', {
      name: 'Dismissed, count unavailable',
    }),
  ).toBeInTheDocument()
  expect(queries).toContain('?customer=acme&triage_state=new')
  expect(queries).toContain('?customer=acme&triage_state=linked')

  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  await waitFor(() =>
    expect(
      queries.filter((query) => query.includes('dismissed')).length,
    ).toBeGreaterThan(1),
  )
})

test('the Filters button shows hidden filters and how many are active', async () => {
  stubApi({
    [reportsPath]: () => page([listItem]),
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?customer=acme&source_kind=slack')
  const toggle = await screen.findByRole('button', {
    name: 'Filters, 2 active',
  })
  expect(toggle).toHaveAttribute('aria-expanded', 'false')
  const filters = document.getElementById(toggle.getAttribute('aria-controls')!)
  expect(filters).toHaveClass('max-md:hidden')
  fireEvent.click(toggle)
  expect(toggle).toHaveAttribute('aria-expanded', 'true')
  expect(filters).not.toHaveClass('max-md:hidden')
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
    [reportsPath]: (url) => {
      if (url.searchParams.has('triage_state')) return page([listItem])
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

test('explains an unknown triage state from the URL', async () => {
  stubApi({
    [reportsPath]: () =>
      json(
        { detail: 'Check the submitted fields.', reason: 'invalid_request' },
        400,
      ),
    [membersPath]: () => json([]),
  })
  renderWorkspaceRoutes(routes, '/inbox?triage_state=archived')
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
    permalink_error: '',
    author_display_name: 'Grace',
    snapshot_text: 'Customer says export is broken',
    captured_at: '2026-09-20T10:00:00Z',
  },
  submitted_by: { id: 'mem-1', display_name: 'Unnamed member' },
  problem: { id: 'prob-1', title: 'Exports time out', state: 'open' },
  triage_state: 'linked',
  follow_up_revision: null,
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
  expect(within(panel).getByText('Unnamed member')).toBeInTheDocument()
  expect(
    within(panel).getByText('Ada Lovelace', { selector: 'dd' }),
  ).toBeInTheDocument()
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
  // Triage comes before the report details.
  const triage = within(panel).getByRole('region', { name: 'Triage' })
  expect(
    triage.compareDocumentPosition(within(panel).getByText('CRM-42')) &
      Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
})

test('a failed Slack permalink can be retried', async () => {
  let permalink = ''
  stubApi({
    [reportsPath]: () => page([listItem]),
    [membersPath]: () => json([]),
    'GET /api/workspaces/ws-1/reports/rep-1/': () =>
      json({
        ...detail,
        provenance: {
          ...detail.provenance,
          permalink,
          permalink_error: permalink ? '' : 'message_not_found',
        },
      }),
    'POST /api/workspaces/ws-1/reports/rep-1/permalink/retry/': () => {
      permalink = detail.provenance.permalink
      return json({ permalink, permalink_error: '' })
    },
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  const panel = await screen.findByRole('region', { name: 'Report detail' })
  const source = await within(panel).findByRole('region', {
    name: 'Provenance',
  })
  expect(source).toHaveTextContent('Slack did not return a link')
  fireEvent.click(within(source).getByRole('button', { name: 'Try again' }))
  expect(
    await within(source).findByRole('link', { name: /Open original message/ }),
  ).toHaveAttribute('href', detail.provenance.permalink)
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
    await screen.findByText(/Manual entry by Unnamed member/),
  ).toBeInTheDocument()
  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox/gone')
  expect(await screen.findByText('Report not found')).toBeInTheDocument()
})
