import { fireEvent, screen, within } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { ProblemListItem } from '@/api/problems'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ProblemPicker } from './problem-picker'

const emptyProblem: ProblemListItem = {
  id: 'prob-empty',
  title: 'Empty problem',
  summary_excerpt: '',
  state: 'open',
  owner: null,
  report_count: 0,
  needs_review: false,
  created_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
}

test('keeps an empty problem selectable without a No reports badge', async () => {
  stubApi({
    'GET /api/workspaces/ws-1/problems/': () =>
      json({ count: 1, next: null, previous: null, results: [emptyProblem] }),
  })
  const onSelect = vi.fn()
  renderWorkspaceRoutes(
    [
      {
        path: '/picker',
        element: <ProblemPicker workspaceId="ws-1" onSelect={onSelect} />,
      },
    ],
    '/picker',
  )

  const radio = await screen.findByRole('radio')
  expect(radio).toBeEnabled()
  const row = radio.closest('label')
  expect(row).not.toBeNull()
  expect(within(row!).getByText('0 reports')).toBeInTheDocument()
  expect(within(row!).queryByText('No reports', { exact: true })).toBeNull()

  fireEvent.click(radio)
  expect(onSelect).toHaveBeenCalledWith(emptyProblem)
})
