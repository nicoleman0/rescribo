import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ProblemDetail } from '@/api/problems'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { GitHubIssueCreate } from './github-issue-create'

const base = '/api/workspaces/ws-1/problems/prob-1/issue'
const problem: ProblemDetail = {
  id: 'prob-1',
  title: 'Export fails',
  summary: 'Export stops at 50%.',
  state: 'in_progress',
  owner: null,
  report_count: 1,
  needs_review: false,
  resolution_revision: 0,
  version: 3,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  engineering_issue: null,
  current_create_operation: null,
}

const draft = (title: string, body: string, id = 'draft-1', version = 1) => ({
  id,
  draft_version: version,
  expires_at: '2026-09-20T10:15:00Z',
  title,
  body,
  marker: `<!-- rescribo-operation:${id} -->`,
  repository: 'acme/widgets',
  visibility: 'private',
})

test('shows the exact persisted preview and posts only after explicit approval', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const previewBodies: string[] = []
  let approvalBody: Record<string, unknown> | undefined
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    [`POST ${base}/preview/`]: (_url, init) => {
      const body = JSON.parse(String(init?.body)) as {
        title?: string
        body?: string
        draft_id?: string
      }
      previewBodies.push(JSON.stringify(body))
      return json(
        draft(
          body.title ?? 'Export fails',
          body.body ?? problem.summary,
          body.draft_id ?? 'draft-1',
          previewBodies.length,
        ),
        201,
      )
    },
    [`POST ${base}/approve/`]: (_url, init) => {
      approvalBody = JSON.parse(String(init?.body)) as Record<string, unknown>
      return json(
        {
          id: 'op-1',
          state: 'queued',
          destination: 'acme/widgets',
          remote_issue_id: '',
          remote_number: null,
          remote_url: '',
          safe_error: '',
          created_at: '2026-09-20T10:00:00Z',
          approved_at: '2026-09-20T10:00:01Z',
          completed_at: null,
        },
        202,
      )
    },
    [`GET ${base}/operations/op-1/`]: () =>
      json({
        id: 'op-1',
        state: 'queued',
        destination: 'acme/widgets',
        remote_issue_id: '',
        remote_number: null,
        remote_url: '',
        safe_error: '',
        created_at: '2026-09-20T10:00:00Z',
        approved_at: '2026-09-20T10:00:01Z',
        completed_at: null,
      }),
  })
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: <GitHubIssueCreate workspaceId="ws-1" problem={problem} />,
      },
    ],
    '/problems/prob-1',
  )

  fireEvent.click(
    await screen.findByRole('button', { name: 'Create GitHub issue' }),
  )
  fireEvent.change(
    await screen.findByRole('textbox', { name: 'Issue title' }),
    {
      target: { value: 'Reviewed export issue' },
    },
  )
  fireEvent.change(screen.getByRole('textbox', { name: 'Issue body' }), {
    target: { value: 'Edited text without customer data' },
  })
  expect(
    screen.queryByRole('button', { name: 'Publish issue' }),
  ).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Preview issue' }))

  expect(await screen.findByText('Exact preview')).toBeInTheDocument()
  expect(screen.getByText('Reviewed export issue')).toBeInTheDocument()
  expect(screen.getAllByText('Edited text without customer data')).toHaveLength(
    2,
  )
  expect(
    screen.getByText('<!-- rescribo-operation:draft-1 -->'),
  ).toBeInTheDocument()
  expect(previewBodies).toHaveLength(2)
  expect(JSON.parse(previewBodies[1])).toMatchObject({ draft_id: 'draft-1' })
  fireEvent.click(screen.getByRole('button', { name: 'Publish issue' }))

  await waitFor(() =>
    expect(approvalBody).toEqual({
      draft_id: 'draft-1',
      draft_version: 2,
      approved: true,
    }),
  )
  expect(
    await screen.findByText('Issue creation is queued.'),
  ).toBeInTheDocument()
})
