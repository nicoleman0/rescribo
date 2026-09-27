import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type {
  ProblemActivity,
  ProblemDetail,
  ProblemListItem,
} from '@/api/problems'
import type { ReportDetail } from '@/api/reports'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ProblemDetailPage } from './problem-detail-page'
import { ProblemsPage } from './problems-page'

const ada = { id: 'mem-2', display_name: 'Ada Lovelace' }
const base = '/api/workspaces/ws-1'

const listItem: ProblemListItem = {
  id: 'prob-1',
  title: 'Exports fail',
  summary_excerpt: 'CSV exports stop half way.',
  state: 'in_progress',
  owner: ada,
  report_count: 2,
  needs_review: true,
  created_at: '2026-09-20T10:00:00Z',
}

const detail: ProblemDetail = {
  id: 'prob-1',
  title: 'Exports fail',
  summary: 'CSV exports stop half way.',
  state: 'open',
  owner: null,
  report_count: 1,
  needs_review: false,
  resolution_revision: 0,
  version: 2,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
}

const linkedReport: ReportDetail = {
  id: 'rep-1',
  title: 'Acme cannot export',
  description: '',
  customer_label: 'Acme',
  customer_contact_reference: '',
  affected_version: '',
  triage_state: 'linked',
  provenance: {
    kind: 'slack',
    permalink: 'javascript:alert(1)',
    author_display_name: 'Sam',
    snapshot_text: '<b>Export is broken</b>',
    captured_at: '2026-09-20T10:00:00Z',
  },
  submitted_by: ada,
  assignee: null,
  problem: { id: 'prob-1', title: 'Exports fail', state: 'open' },
  version: 2,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
}

const activity = (changes: Partial<ProblemActivity>): ProblemActivity => ({
  id: crypto.randomUUID(),
  action: 'problem.created',
  actor: ada,
  actor_system: '',
  created_at: '2026-09-20T10:00:00Z',
  report: null,
  from_problem: null,
  to_problem: null,
  from_assignee: null,
  to_assignee: null,
  changed_fields: [],
  state: null,
  ...changes,
})

const page = <T,>(results: T[], extra = {}) =>
  json({ count: results.length, next: null, previous: null, results, ...extra })

const listRoutes = [{ path: '/problems', element: <ProblemsPage /> }]
const detailRoutes = [
  { path: '/problems/:problemId', element: <ProblemDetailPage /> },
]

test('lists problems with owner, state, count, and review flag, and searches', async () => {
  const queries: string[] = []
  stubApi({
    [`GET ${base}/problems/`]: (url) => {
      queries.push(url.search)
      return url.searchParams.get('q') === 'nothing'
        ? page([])
        : page([listItem])
    },
  })
  renderWorkspaceRoutes(listRoutes, '/problems')
  const list = await screen.findByRole('list', { name: 'Problems' })
  const link = within(list).getByRole('link', { name: /Exports fail/ })
  expect(link).toHaveAttribute('href', '/problems/prob-1')
  expect(within(link).getByText('Needs review')).toBeInTheDocument()
  expect(within(link).getByText('In progress')).toBeInTheDocument()
  expect(within(link).getByText('Owner: Ada Lovelace')).toBeInTheDocument()
  expect(within(link).getByText('2 reports')).toBeInTheDocument()

  fireEvent.change(screen.getByRole('searchbox', { name: 'Search problems' }), {
    target: { value: ' nothing ' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Search' }))
  expect(
    await screen.findByText('No problems match this search'),
  ).toBeInTheDocument()
  expect(queries.at(-1)).toBe('?q=nothing')
  expect(screen.getByTestId('location')).toHaveTextContent(
    '/problems?q=nothing',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Clear search' }))
  await screen.findByRole('list', { name: 'Problems' })
})

test('distinguishes no problems, an invalid search, and a failed load', async () => {
  let status = 200
  stubApi({
    [`GET ${base}/problems/`]: () =>
      status === 200
        ? page([])
        : json({ detail: 'x', reason: 'invalid_request' }, status),
  })
  const view = renderWorkspaceRoutes(listRoutes, '/problems')
  expect(await screen.findByText('No problems yet')).toBeInTheDocument()
  view.unmount()
  status = 400
  const invalid = renderWorkspaceRoutes(listRoutes, '/problems?q=x')
  expect(
    await screen.findByText('This search is not valid'),
  ).toBeInTheDocument()
  invalid.unmount()
  status = 503
  renderWorkspaceRoutes(listRoutes, '/problems')
  expect(await screen.findByText('Could not load problems')).toBeInTheDocument()
  status = 200
  fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('No problems yet')).toBeInTheDocument()
})

function stubDetail(problem: ProblemDetail = detail) {
  document.cookie = 'csrftoken=csrf-token'
  const server = { problem }
  const sent: Record<string, unknown>[] = []
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/members/`]: () => json([ada]),
    [`GET ${base}/problems/prob-1/`]: () => json(server.problem),
    [`GET ${base}/problems/prob-1/reports/`]: () => page([linkedReport]),
    [`GET ${base}/problems/prob-1/activity/`]: () =>
      page([
        activity({
          action: 'report.unlinked',
          report: { id: 'rep-9', title: 'Moved away' },
          to_problem: { id: 'prob-2', title: 'Billing' },
        }),
        activity({
          action: 'report.assigned',
          report: { id: 'rep-1', title: 'Acme cannot export' },
          to_assignee: ada,
        }),
        activity({ action: 'report.linked', report: null }),
        activity({ action: 'problem.updated', changed_fields: ['owner'] }),
        activity({ actor: null, actor_system: 'github' }),
      ]),
    [`POST ${base}/problems/prob-1/edit/`]: (_url, init) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      sent.push(body)
      if (sent.length === 1) {
        server.problem = { ...problem, summary: 'Theirs', version: 3 }
        return json(
          {
            detail: 'Changed.',
            reason: 'version_conflict',
            field_errors: {},
            current: server.problem,
          },
          409,
        )
      }
      server.problem = { ...server.problem, ...body, version: 4 }
      return json(server.problem)
    },
  })
  return { sent }
}

test('shows linked reports with provenance and a readable activity history', async () => {
  stubDetail()
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1')
  expect(
    await screen.findByRole('heading', { level: 1, name: 'Exports fail' }),
  ).toBeInTheDocument()
  expect(screen.getByText('1 report · v2')).toBeInTheDocument()
  const reports = await screen.findByRole('list', { name: 'Linked reports' })
  expect(
    within(reports).getByRole('link', { name: 'Acme cannot export' }),
  ).toHaveAttribute('href', '/inbox/rep-1')
  // Captured text stays text, and an unsafe permalink is not rendered.
  expect(
    within(reports).getByText('<b>Export is broken</b>'),
  ).toBeInTheDocument()
  expect(
    within(reports).getByText('The message link is not available yet.'),
  ).toBeInTheDocument()
  expect(within(reports).getByLabelText('Assignee')).toBeInTheDocument()

  const history = await screen.findByRole('list', { name: 'Problem activity' })
  const entries = within(history).getAllByRole('listitem')
  expect(entries.map((entry) => entry.textContent)).toEqual([
    expect.stringContaining('Ada Lovelace moved Moved away to Billing'),
    expect.stringContaining(
      'Ada Lovelace assigned Acme cannot export to Ada Lovelace',
    ),
    expect.stringContaining('Ada Lovelace linked a report'),
    expect.stringContaining('Ada Lovelace changed the owner'),
    expect.stringContaining('github created the problem'),
  ])
  expect(
    within(history).getByRole('link', { name: 'Billing' }),
  ).toHaveAttribute('href', '/problems/prob-2')
})

test('keeps an edit draft on conflict and retries against the current version', async () => {
  const { sent } = stubDetail()
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1')
  fireEvent.click(
    await screen.findByRole('button', { name: 'Edit title and summary' }),
  )
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'Exports stall' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  expect(
    await screen.findByText('The problem was not saved'),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Exports stall')
  expect(await screen.findByText('1 report · v3')).toBeInTheDocument()
  expect(sent).toEqual([{ expected_version: 2, title: 'Exports stall' }])
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  expect(
    await screen.findByRole('heading', { level: 1, name: 'Exports stall' }),
  ).toBeInTheDocument()
  // Only the changed title is sent, so the other member's summary survives.
  expect(sent[1]).toEqual({ expected_version: 3, title: 'Exports stall' })
  expect(screen.getByText('Theirs')).toBeInTheDocument()
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Edit title and summary' }),
    ).toHaveFocus(),
  )
})

test('reports a missing problem', async () => {
  stubApi({
    [`GET ${base}/problems/prob-1/`]: () =>
      json({ detail: 'Not found.', reason: 'not_found' }, 404),
  })
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1')
  expect(await screen.findByText('Problem not found')).toBeInTheDocument()
})
