import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'
import type {
  ProblemActivity,
  ProblemDetail,
  ProblemListItem,
} from '@/api/problems'
import type { ReportDetail } from '@/api/reports'
import { problemKeys } from '@/api/problems'
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
  engineering_issue: null,
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
  fix_note: '',
  fix_version: '',
  fix_evidence_url: '',
  fix_confirmed_at: null,
  fix_confirmed_by: null,
  version: 2,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
}

const linkedReport: ReportDetail = {
  id: 'rep-1',
  title: 'Acme cannot export',
  description: '',
  customer_label: 'Acme',
  customer_contact_reference: '',
  affected_version: '',
  triage_state: 'linked',
  follow_up_revision: null,
  provenance: {
    kind: 'slack',
    permalink: 'javascript:alert(1)',
    permalink_error: '',
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

test('keeps the edit draft mounted across a failed background refresh and retry', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  let reads = 0
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/problems/prob-1/`]: () => {
      reads += 1
      return reads >= 2 && reads <= 4
        ? json({ detail: 'Unavailable' }, 503)
        : json(detail)
    },
    [`GET ${base}/members/`]: () => json([ada]),
    [`GET ${base}/problems/prob-1/reports/`]: () => page([linkedReport]),
    [`GET ${base}/problems/prob-1/activity/`]: () => page([]),
  })
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1', client)
  fireEvent.click(
    await screen.findByRole('button', { name: 'Edit title and summary' }),
  )
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: 'My unsaved title' },
  })

  await client.refetchQueries({
    queryKey: problemKeys.detail('ws-1', 'prob-1'),
  })
  expect(
    await screen.findByText('Could not refresh this problem'),
  ).toBeVisible()
  expect(screen.getByLabelText('Title')).toHaveValue('My unsaved title')

  fireEvent.click(
    within(
      screen
        .getByText('Could not refresh this problem')
        .closest('[role="alert"]') as HTMLElement,
    ).getByRole('button', { name: 'Try again' }),
  )
  await waitFor(() => expect(reads).toBe(5))
  expect(screen.getByLabelText('Title')).toHaveValue('My unsaved title')
})

test('submits required fix details and optional evidence, then shows confirmed fix', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const server: { problem: ProblemDetail } = {
    problem: { ...detail, state: 'in_progress' },
  }
  const sent: Record<string, unknown>[] = []
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/members/`]: () => json([ada]),
    [`GET ${base}/problems/prob-1/`]: () => json(server.problem),
    [`GET ${base}/problems/prob-1/reports/`]: () => page([linkedReport]),
    [`GET ${base}/problems/prob-1/activity/`]: () => page([]),
    [`POST ${base}/problems/prob-1/confirm-fix/`]: (_url, init) => {
      const body = JSON.parse(String(init?.body)) as Record<string, unknown>
      sent.push(body)
      server.problem = {
        ...server.problem,
        state: 'fix_available',
        fix_note: body.fix_note as string,
        fix_version: body.fix_version as string,
        fix_evidence_url: (body.evidence_url as string) ?? '',
        version: server.problem.version + 1,
      }
      return json(server.problem)
    },
  })
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1')
  await screen.findByRole('heading', { name: 'Exports fail' })
  expect(screen.getByLabelText('Fix details')).toBeRequired()
  expect(screen.getByLabelText('Available in version')).toBeRequired()
  fireEvent.change(screen.getByLabelText('Fix details'), {
    target: { value: 'CSV export now completes' },
  })
  fireEvent.change(screen.getByLabelText('Available in version'), {
    target: { value: '2.4.0' },
  })
  fireEvent.change(screen.getByLabelText('Evidence URL'), {
    target: { value: 'https://example.com/release' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm fix' }))
  expect(await screen.findByText('Fix available')).toBeInTheDocument()
  expect(sent).toEqual([
    {
      expected_version: 2,
      fix_note: 'CSV export now completes',
      fix_version: '2.4.0',
      evidence_url: 'https://example.com/release',
    },
  ])
})

test('confirms applicability for a report linked after fix availability', async () => {
  document.cookie = 'csrftoken=csrf-token'
  let followUpRevision: number | null = null
  const fixedProblem: ProblemDetail = {
    ...detail,
    state: 'fix_available',
    resolution_revision: 1,
    fix_note: 'Export corrected',
    fix_version: '2.4.0',
  }
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/members/`]: () => json([ada]),
    [`GET ${base}/problems/prob-1/`]: () => json(fixedProblem),
    [`GET ${base}/problems/prob-1/reports/`]: () =>
      page([{ ...linkedReport, follow_up_revision: followUpRevision }]),
    [`GET ${base}/problems/prob-1/activity/`]: () => page([]),
    [`POST ${base}/reports/rep-1/confirm-fix-applies/`]: (_url, init) => {
      expect(JSON.parse(String(init?.body))).toEqual({
        expected_version: linkedReport.version,
        expected_resolution_revision: 1,
      })
      followUpRevision = 1
      return json({ ...linkedReport, follow_up_revision: followUpRevision })
    },
  })
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1')
  fireEvent.click(
    await screen.findByRole('button', { name: 'Confirm fix applies' }),
  )
  await waitFor(() => expect(followUpRevision).toBe(1))
  await waitFor(() =>
    expect(
      screen.queryByRole('button', { name: 'Confirm fix applies' }),
    ).not.toBeInTheDocument(),
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

test('shows only the refresh alert when an activity refetch fails with data', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  let reads = 0
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/problems/prob-1/`]: () => json(detail),
    [`GET ${base}/members/`]: () => json([ada]),
    [`GET ${base}/problems/prob-1/reports/`]: () => page([linkedReport]),
    [`GET ${base}/problems/prob-1/activity/`]: () => {
      reads += 1
      return reads === 1
        ? page([activity({ action: 'problem.updated' })])
        : json({ detail: 'Unavailable' }, 503)
    },
  })
  renderWorkspaceRoutes(detailRoutes, '/problems/prob-1', client)
  await screen.findByRole('list', { name: 'Problem activity' })
  await client.refetchQueries({
    queryKey: problemKeys.activity('ws-1', 'prob-1', 1),
  })
  expect(await screen.findByText('Could not refresh activity')).toBeVisible()
  expect(screen.queryByText('Could not load activity')).not.toBeInTheDocument()
})
