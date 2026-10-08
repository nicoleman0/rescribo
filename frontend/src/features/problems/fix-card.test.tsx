import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ProblemDetail } from '@/api/problems'
import { renderWorkspaceRoutes } from '@/test/render'
import { FixCard } from './problem-detail-page'

const problem: ProblemDetail = {
  id: 'prob-1',
  title: 'Export fails',
  summary: 'Export stops.',
  state: 'fix_available',
  owner: null,
  report_count: 1,
  needs_review: false,
  resolution_revision: 1,
  fix_note: 'Fixed',
  fix_version: '4.13',
  fix_evidence_url: '',
  fix_confirmed_at: '2026-10-01T10:00:00Z',
  fix_confirmed_by: null,
  version: 2,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
  fix_release: {
    provider: 'github',
    tag_name: 'v4.13',
    name: '4.13',
    url: 'https://github.com/acme/widgets/releases/tag/v4.13',
    published_at: '2026-10-01T12:00:00Z',
    linked_by: { id: 'm-1', display_name: 'Ada' },
    linked_at: '2026-10-01T12:01:00Z',
  },
}

test('shows the linked release snapshot on the confirmed fix card', () => {
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: <FixCard workspaceId="ws-1" problem={problem} />,
      },
    ],
    '/problems/prob-1',
  )
  const release = screen.getByRole('link', { name: /v4.13/ })
  expect(release).toHaveAttribute('href', problem.fix_release?.url)
  expect(release).toHaveAttribute('target', '_blank')
  expect(screen.getByText('4.13')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Change release' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Remove release' })).toBeVisible()
})
