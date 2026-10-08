import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ProblemActivityList } from './problem-activity'

test('describes linked and removed releases in activity', async () => {
  stubApi({
    'GET /api/workspaces/ws-1/problems/prob-1/activity/': () =>
      json({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 'act-2',
            action: 'problem.fix_release_linked',
            actor: { id: 'm-1', display_name: 'Ada' },
            actor_system: '',
            created_at: '2026-10-02T12:00:00Z',
            report: null,
            from_problem: null,
            to_problem: null,
            from_assignee: null,
            to_assignee: null,
            changed_fields: [],
            state: null,
            metadata: { tag_name: 'v4.13' },
          },
          {
            id: 'act-1',
            action: 'problem.fix_release_unlinked',
            actor: { id: 'm-1', display_name: 'Ada' },
            actor_system: '',
            created_at: '2026-10-02T11:00:00Z',
            report: null,
            from_problem: null,
            to_problem: null,
            from_assignee: null,
            to_assignee: null,
            changed_fields: [],
            state: null,
            metadata: {},
          },
        ],
      }),
  })
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: <ProblemActivityList workspaceId="ws-1" problemId="prob-1" />,
      },
    ],
    '/problems/prob-1',
  )
  expect(await screen.findByText('linked release v4.13')).toBeVisible()
  expect(screen.getByText('removed the linked release')).toBeVisible()
})
