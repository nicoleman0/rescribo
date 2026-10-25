import { useQuery } from '@tanstack/react-query'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ProblemDetail } from '@/api/problems'
import { problemKeys } from '@/api/problems'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { DeclineProblemForm, ProblemStatusCard } from './problem-status'

const initial: ProblemDetail = {
  id: 'prob-1',
  title: 'Export fails',
  summary: '',
  state: 'open',
  owner: null,
  report_count: 0,
  needs_review: false,
  not_planned_reason: '',
  resolution_revision: 0,
  fix_note: '',
  fix_version: '',
  fix_evidence_url: '',
  fix_confirmed_at: null,
  fix_confirmed_by: null,
  version: 1,
  created_at: '2026-10-01T10:00:00Z',
  updated_at: '2026-10-01T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
}

const server = { problem: initial }
function Card({ problem = initial }: { problem?: ProblemDetail }) {
  const { data } = useQuery({
    queryKey: problemKeys.detail('ws-1', problem.id),
    queryFn: () => Promise.resolve(server.problem),
    initialData: problem,
    staleTime: Infinity,
  })
  return data ? <ProblemStatusCard workspaceId="ws-1" problem={data} /> : null
}

function renderCard(problem = initial) {
  server.problem = problem
  return renderWorkspaceRoutes(
    [{ path: '/problems/prob-1', element: <Card problem={problem} /> }],
    '/problems/prob-1',
  )
}

test.each([
  ['open', 'Start work'],
  ['in_progress', 'Move back to open'],
  ['not_planned', 'Reopen'],
] as const)('offers the state action for %s', async (state, label) => {
  renderCard({ ...initial, state })
  expect(await screen.findByRole('button', { name: label })).toBeVisible()
})

test('shows the decline reason and hides the card for a fixed problem', async () => {
  const { unmount } = renderCard({
    ...initial,
    state: 'not_planned',
    not_planned_reason: 'No longer needed',
  })
  expect(await screen.findByText('No longer needed')).toBeVisible()
  expect(await screen.findByRole('button', { name: 'Reopen' })).toBeVisible()
  unmount()
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: (
          <ProblemStatusCard
            workspaceId="ws-1"
            problem={{ ...initial, state: 'fix_available' }}
          />
        ),
      },
    ],
    '/problems/prob-1',
  )
  expect(
    screen.queryByRole('heading', { name: 'Status' }),
  ).not.toBeInTheDocument()
})

test('decline requires a nonblank reason and keeps it after a conflict', async () => {
  const current = { ...initial, version: 2 }
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    'POST /api/workspaces/ws-1/problems/prob-1/state/': () =>
      json({ detail: 'Conflict', reason: 'version_conflict', current }, 409),
  })
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: (
          <DeclineProblemForm
            workspaceId="ws-1"
            problem={initial}
            onCancel={() => undefined}
          />
        ),
      },
    ],
    '/problems/prob-1',
  )
  const submit = screen.getByRole('button', { name: 'Mark not planned' })
  expect(submit).toBeDisabled()
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason' }), {
    target: { value: 'No longer needed' },
  })
  expect(submit).toBeEnabled()
  fireEvent.click(submit)
  expect(await screen.findByText('The problem was not changed')).toBeVisible()
  expect(screen.getByRole('textbox', { name: 'Reason' })).toHaveValue(
    'No longer needed',
  )
})

test('a successful state action focuses the card heading', async () => {
  const updated = { ...initial, state: 'in_progress' as const, version: 2 }
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    'POST /api/workspaces/ws-1/problems/prob-1/state/': (_url, init) => {
      expect(JSON.parse(String(init?.body))).toEqual({
        expected_version: 1,
        action: 'start',
      })
      server.problem = updated
      return json(updated)
    },
  })
  renderCard()
  fireEvent.click(await screen.findByRole('button', { name: 'Start work' }))
  const heading = await screen.findByRole('heading', { name: 'Status' })
  await waitFor(() => expect(heading).toHaveFocus())
  expect(
    screen.getByRole('button', { name: 'Move back to open' }),
  ).toBeVisible()
})
