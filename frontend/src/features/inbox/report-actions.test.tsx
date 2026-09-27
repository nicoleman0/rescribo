import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ProblemListItem } from '@/api/problems'
import type { ReportDetail } from '@/api/reports'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ReportDetailPanel } from './report-detail'

const ada = { id: 'mem-2', display_name: 'Ada Lovelace' }
const grace = { id: 'mem-3', display_name: 'Grace Hopper' }

const report: ReportDetail = {
  id: 'rep-1',
  title: 'CSV export fails',
  description: 'Stops at 50%',
  customer_label: 'Acme',
  customer_contact_reference: 'CRM-1',
  affected_version: '2.3',
  triage_state: 'new',
  provenance: {
    kind: 'manual',
    permalink: '',
    author_display_name: '',
    snapshot_text: '',
    captured_at: '2026-09-20T10:00:00Z',
  },
  submitted_by: ada,
  assignee: null,
  problem: null,
  version: 3,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
}

const problem: ProblemListItem = {
  id: 'prob-1',
  title: 'Exports fail',
  summary_excerpt: '',
  state: 'open',
  owner: null,
  report_count: 2,
  needs_review: false,
  created_at: '2026-09-20T10:00:00Z',
}

const base = '/api/workspaces/ws-1'
const routes = [
  {
    path: '/inbox/:reportId',
    element: <ReportDetailPanel workspaceId="ws-1" reportId="rep-1" />,
  },
]

type Body = Record<string, unknown>
type Server = { report: ReportDetail }
type Action = (body: Body, server: Server) => Response | Promise<Response>

/** Stub the report API. The GET returns whatever the server state holds, so
 * refetches after a mutation see the same data the action returned. */
function stubReport(
  initial: ReportDetail,
  actions: Record<string, Action> = {},
  problems: ProblemListItem[] = [problem],
) {
  document.cookie = 'csrftoken=csrf-token'
  const server: Server = { report: initial }
  const sent: { path: string; body: Body }[] = []
  const handlers: Parameters<typeof stubApi>[0] = {
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/reports/rep-1/`]: () => json(server.report),
    [`GET ${base}/members/`]: () => json([ada, grace]),
    [`GET ${base}/problems/`]: () =>
      json({
        count: problems.length,
        next: null,
        previous: null,
        results: problems,
      }),
  }
  for (const [action, respond] of Object.entries(actions)) {
    handlers[`POST ${base}/reports/rep-1/${action}/`] = (_url, init) => {
      const body = JSON.parse(String(init?.body)) as Body
      sent.push({ path: action, body })
      return respond(body, server)
    }
  }
  stubApi(handlers)
  return { sent, server }
}

/** Accept the action: store the updated report and return it. */
const accept =
  (changes: Partial<ReportDetail>, status = 200): Action =>
  (_body, server) => {
    server.report = {
      ...server.report,
      ...changes,
      version: server.report.version + 1,
    }
    return json(server.report, status)
  }

const triage = () => screen.getByRole('region', { name: 'Triage' })

test('offers actions that match the report state', async () => {
  stubReport(report)
  const view = renderWorkspaceRoutes(routes, '/inbox/rep-1')
  await screen.findByRole('region', { name: 'Triage' })
  for (const name of ['Link to problem', 'Create problem', 'Dismiss']) {
    expect(within(triage()).getByRole('button', { name })).toBeEnabled()
  }
  view.unmount()

  stubReport({
    ...report,
    triage_state: 'linked',
    problem: { id: 'prob-1', title: 'Exports fail', state: 'fix_available' },
  })
  const linked = renderWorkspaceRoutes(routes, '/inbox/rep-1')
  await screen.findByRole('region', { name: 'Triage' })
  for (const name of ['Move to problem', 'Move to new problem', 'Ungroup']) {
    expect(within(triage()).getByRole('button', { name })).toBeEnabled()
  }
  expect(screen.getByRole('link', { name: 'Exports fail' })).toHaveAttribute(
    'href',
    '/problems/prob-1',
  )
  expect(screen.getByText('Check that the fix applies')).toBeInTheDocument()
  linked.unmount()

  stubReport({ ...report, triage_state: 'dismissed' })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  await screen.findByRole('region', { name: 'Triage' })
  expect(
    within(triage()).getByRole('button', { name: 'Restore report' }),
  ).toBeEnabled()
  expect(
    within(triage()).queryByRole('button', { name: 'Link to problem' }),
  ).toBeNull()
})

test('creates and links a problem in one request from the report title', async () => {
  const { sent } = stubReport(report, {
    'create-problem': accept(
      {
        triage_state: 'linked',
        problem: { id: 'prob-9', title: 'Exports', state: 'open' },
      },
      201,
    ),
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Create problem' }))
  const title = screen.getByLabelText('Problem title')
  expect(title).toHaveValue('CSV export fails')
  expect(screen.getByLabelText('Summary')).toHaveValue('')
  fireEvent.change(title, { target: { value: 'Exports' } })
  await screen.findByRole('option', { name: 'Grace Hopper' })
  fireEvent.change(screen.getByLabelText('Owner'), {
    target: { value: 'mem-3' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create and link' }))
  await screen.findByRole('button', { name: 'Ungroup' })
  expect(sent).toEqual([
    {
      path: 'create-problem',
      body: {
        expected_version: 3,
        title: 'Exports',
        summary: '',
        owner_id: 'mem-3',
      },
    },
  ])
})

test('links to a chosen problem from the picker', async () => {
  const { sent } = stubReport(report, {
    link: accept({
      triage_state: 'linked',
      problem: { id: 'prob-1', title: 'Exports fail', state: 'open' },
    }),
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(
    await screen.findByRole('button', { name: 'Link to problem' }),
  )
  const submit = screen.getByRole('button', { name: 'Link report' })
  expect(submit).toBeDisabled()
  fireEvent.click(await screen.findByRole('radio', { name: /Exports fail/ }))
  expect(screen.getByText('2 reports')).toBeInTheDocument()
  fireEvent.click(submit)
  await screen.findByRole('button', { name: 'Ungroup' })
  expect(sent).toEqual([
    { path: 'link', body: { expected_version: 3, problem_id: 'prob-1' } },
  ])
})

test('explains an empty picker', async () => {
  stubReport(report, {}, [])
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(
    await screen.findByRole('button', { name: 'Link to problem' }),
  )
  expect(
    await screen.findByText(/There are no other problems yet/),
  ).toBeInTheDocument()
})

test('locks actions while a dismissal is pending', async () => {
  let finish: () => void = () => {}
  const { sent } = stubReport(report, {
    dismiss: (body, server) =>
      new Promise<Response>((resolve) => {
        finish = () =>
          resolve(accept({ triage_state: 'dismissed' })(body, server))
      }),
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Dismiss' }))
  expect(await screen.findByRole('button', { name: 'Saving…' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Link to problem' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Saving…' }))
  finish()
  await screen.findByRole('button', { name: 'Restore report' })
  expect(sent).toHaveLength(1)
})

test('shows the current report on a stale assignment and retries only on request', async () => {
  let calls = 0
  const { sent } = stubReport(report, {
    assign: (body, server) => {
      calls += 1
      if (calls === 1) {
        // Another member reassigned the report first.
        server.report = { ...report, assignee: grace, version: 5 }
        return json(
          {
            detail: 'Changed.',
            reason: 'version_conflict',
            field_errors: {},
            current: server.report,
          },
          409,
        )
      }
      return accept({ assignee: ada })(body, server)
    },
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  await screen.findByRole('option', { name: 'Ada Lovelace' })
  const select = within(triage()).getByLabelText('Assignee')
  fireEvent.change(select, { target: { value: 'mem-2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save assignee' }))
  expect(
    await screen.findByText('The assignee was not changed'),
  ).toBeInTheDocument()
  expect(screen.getByText(/changed while you were working/)).toBeInTheDocument()
  // The detail now shows the other member's decision; the draft is kept.
  expect(await screen.findByText('v5')).toBeInTheDocument()
  expect(select).toHaveValue('mem-2')
  expect(sent).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: 'Save assignee' }))
  await waitFor(() => expect(sent).toHaveLength(2))
  expect(sent[1].body).toEqual({ expected_version: 5, assignee_id: 'mem-2' })
})

test('keeps the new problem draft on network and field errors', async () => {
  let calls = 0
  stubReport(report, {
    'create-problem': () => {
      calls += 1
      if (calls === 1) throw new TypeError('Failed to fetch')
      return json(
        {
          detail: 'Choose.',
          reason: 'invalid_reference',
          field_errors: { owner_id: ['invalid_reference'] },
        },
        400,
      )
    },
  })
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Create problem' }))
  fireEvent.change(screen.getByLabelText('Problem title'), {
    target: { value: 'Draft title' },
  })
  fireEvent.change(screen.getByLabelText('Summary'), {
    target: { value: 'Draft summary' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create and link' }))
  expect(
    await screen.findByText(/Could not reach Rescribo/),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Problem title')).toHaveValue('Draft title')
  fireEvent.click(screen.getByRole('button', { name: 'Create and link' }))
  expect(
    await screen.findByText('Choose an active record in this workspace.'),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Owner')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByLabelText('Summary')).toHaveValue('Draft summary')
})

test('returns focus to the opener when a panel is cancelled', async () => {
  stubReport(report)
  renderWorkspaceRoutes(routes, '/inbox/rep-1')
  fireEvent.click(
    await screen.findByRole('button', { name: 'Link to problem' }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  await waitFor(() =>
    expect(
      screen.getByRole('button', { name: 'Link to problem' }),
    ).toHaveFocus(),
  )
})
