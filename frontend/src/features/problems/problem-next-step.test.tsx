import { useQuery } from '@tanstack/react-query'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { EngineeringIssue } from '@/api/github-issues'
import { problemKeys, type ProblemDetail } from '@/api/problems'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ProblemNextStep } from './problem-next-step'

const problem: ProblemDetail = {
  id: 'prob-1',
  title: 'Exports fail',
  summary: '',
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
  version: 1,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
}

const issue = {
  number: 42,
  url: 'https://github.com/acme/widgets/issues/42',
} as EngineeringIssue

// Reads the problem from the query cache, as the detail page does, so a
// mutation's result reaches the banner. A refetch returns what the server
// last sent.
let served: ProblemDetail
function Banner({ initial }: { initial: ProblemDetail }) {
  served = initial
  const { data } = useQuery({
    queryKey: problemKeys.detail('ws-1', initial.id),
    queryFn: () => Promise.resolve(served),
    staleTime: Infinity,
  })
  return data ? <ProblemNextStep workspaceId="ws-1" problem={data} /> : null
}

function renderBanner(changes: Partial<ProblemDetail>) {
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: <Banner initial={{ ...problem, ...changes }} />,
      },
    ],
    '/problems/prob-1',
  )
}

function renderStep(changes: Partial<ProblemDetail>) {
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: (
          <ProblemNextStep
            workspaceId="ws-1"
            problem={{ ...problem, ...changes }}
          />
        ),
      },
    ],
    '/problems/prob-1',
  )
  const heading = screen.getByRole('heading', { level: 2 })
  return {
    heading: heading.textContent,
    tone: heading.closest('[data-tone]')?.getAttribute('data-tone'),
    links: screen.queryAllByRole('link').map((link) => link.textContent),
  }
}

test.each([
  [{ state: 'open' }, 'info', 'Confirm the fix when it ships', []],
  [{ state: 'in_progress' }, 'progress', 'Confirm the fix when it ships', []],
  [
    { state: 'in_progress', needs_review: true, engineering_issue: issue },
    'warning',
    'Review the fix',
    ['Open follow-ups', 'Open GitHub issue #42 (opens in a new tab)'],
  ],
  [
    { state: 'fix_available', fix_version: '4.13' },
    'success',
    'Fix available in 4.13',
    ['Open follow-ups'],
  ],
  [
    { state: 'fix_available', needs_review: true },
    'warning',
    'Review the fix',
    ['Open follow-ups'],
  ],
  [{ state: 'not_planned' }, 'neutral', 'Not planned', []],
  [{ state: 'not_planned', needs_review: true }, 'neutral', 'Not planned', []],
] as const)('%j shows the %s tone', (changes, tone, heading, links) => {
  expect(renderStep(changes)).toEqual({ tone, heading, links })
})

test('a fix that needs review says what to check', () => {
  renderStep({ state: 'fix_available', needs_review: true })
  expect(
    screen.getByText(/Check the follow-up outcomes and the GitHub issue/),
  ).toBeInTheDocument()
})

test('offers Mark reviewed only while the problem needs review', async () => {
  renderBanner({ state: 'fix_available', needs_review: false })
  expect(await screen.findByRole('heading', { level: 2 })).toBeVisible()
  expect(
    screen.queryByRole('button', { name: 'Mark reviewed' }),
  ).not.toBeInTheDocument()
})

test.each(['in_progress', 'fix_available', 'not_planned'] as const)(
  'offers Mark reviewed on a flagged %s problem',
  async (state) => {
    renderBanner({ state, needs_review: true })
    expect(
      await screen.findByRole('button', { name: 'Mark reviewed' }),
    ).toBeVisible()
  },
)

test('marking reviewed sends the version and moves to the next step', async () => {
  let submitted: Record<string, unknown> | undefined
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    'POST /api/workspaces/ws-1/problems/prob-1/mark-reviewed/': (
      _url,
      init,
    ) => {
      submitted = JSON.parse(String(init?.body)) as Record<string, unknown>
      served = {
        ...problem,
        state: 'fix_available',
        fix_version: '4.13',
        needs_review: false,
        version: 4,
      }
      return json(served)
    },
  })
  renderBanner({
    state: 'fix_available',
    fix_version: '4.13',
    needs_review: true,
    version: 3,
  })
  fireEvent.click(await screen.findByRole('button', { name: 'Mark reviewed' }))
  const heading = await screen.findByRole('heading', {
    name: 'Fix available in 4.13',
  })
  expect(submitted).toEqual({ expected_version: 3 })
  await waitFor(() => expect(heading).toHaveFocus())
  expect(
    screen.queryByRole('button', { name: 'Mark reviewed' }),
  ).not.toBeInTheDocument()
})

test('a conflict shows the error and the current problem step', async () => {
  const current: ProblemDetail = {
    ...problem,
    state: 'fix_available',
    fix_version: '4.13',
    needs_review: false,
    version: 5,
  }
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    'POST /api/workspaces/ws-1/problems/prob-1/mark-reviewed/': () => {
      served = current
      return json(
        { detail: 'Conflict', reason: 'invalid_transition', current },
        409,
      )
    },
  })
  renderBanner({
    state: 'fix_available',
    fix_version: '4.13',
    needs_review: true,
    version: 4,
  })
  fireEvent.click(await screen.findByRole('button', { name: 'Mark reviewed' }))
  expect(
    await screen.findByText('The problem was not marked reviewed'),
  ).toBeVisible()
  expect(
    screen.getByRole('heading', { name: 'Fix available in 4.13' }),
  ).toBeVisible()
})
