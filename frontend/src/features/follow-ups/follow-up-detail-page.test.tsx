import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { FollowUpDetail } from '@/api/follow-ups'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { FollowUpDetailPage } from './follow-up-detail-page'

const base = '/api/workspaces/ws-1/follow-ups/fu-1'
const routes = [
  { path: 'follow-ups/:followUpId/page', element: <FollowUpDetailPage /> },
]

function detail(): FollowUpDetail {
  return {
    id: 'fu-1',
    report: {
      id: 'rep-1',
      title: 'CSV export fails',
      customer_label: 'Acme',
      triage_state: 'linked',
      version: 1,
      created_at: '2026-09-20T10:00:00Z',
    },
    problem: {
      id: 'prob-1',
      title: 'Exports fail',
      fix_note: 'Fix the parser',
      fix_version: '1.0',
      resolution_revision: 2,
    },
    recipient: {
      member: { id: 'mem-2', display_name: 'Ada Lovelace' },
      has_slack_link: true,
    },
    notification: null,
    outcome: { state: 'pending', note: '', at: null, by: null },
    version: 1,
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-20T10:00:00Z',
    history: [],
  }
}

test('shows the full page and preserves the list query in its back link', async () => {
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail()),
  })
  renderWorkspaceRoutes(
    routes,
    '/follow-ups/fu-1/page?bucket=needs_approval&page=2',
  )
  expect(
    await screen.findByRole('heading', { name: 'CSV export fails', level: 1 }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'Back to follow-ups' }),
  ).toHaveAttribute('href', '/follow-ups?bucket=needs_approval&page=2')
})

test('shows not found and keeps the back link available', async () => {
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json({ detail: 'Not found' }, 404),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1/page')
  expect(await screen.findByText('Follow-up not found')).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'Back to follow-ups' }),
  ).toHaveAttribute('href', '/follow-ups')
})
