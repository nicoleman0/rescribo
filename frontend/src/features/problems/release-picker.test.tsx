import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import type { ProblemDetail } from '@/api/problems'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ReleasePicker } from './release-picker'

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
  fix_release: null,
}
const row = (id: string, tag: string) => ({
  external_id: id,
  tag_name: tag,
  name: tag,
  url: `https://github.com/acme/widgets/releases/tag/${tag}`,
  published_at: '2026-10-01T12:00:00Z',
  prerelease: false,
})

test('lists pages, filters loaded releases, and links the selected ID', async () => {
  let submitted: Record<string, unknown> | undefined
  stubApi({
    'GET /api/auth/csrf/': () => new Response(null, { status: 204 }),
    'GET /api/workspaces/ws-1/releases/': (url) =>
      json(
        url.searchParams.get('page') === '2'
          ? { results: [row('102', 'v4.14')], has_next: false }
          : { results: [row('101', 'v4.13')], has_next: true },
      ),
    'POST /api/workspaces/ws-1/problems/prob-1/fix-release/': (_url, init) => {
      submitted = JSON.parse(String(init?.body)) as Record<string, unknown>
      return json({
        ...problem,
        version: 3,
        fix_release: {
          provider: 'github',
          tag_name: 'v4.14',
          name: 'v4.14',
          url: row('102', 'v4.14').url,
          published_at: '2026-10-01T12:00:00Z',
          linked_by: { id: 'm-1', display_name: 'Ada' },
          linked_at: '2026-10-02T12:00:00Z',
        },
      })
    },
  })
  const onCancel = vi.fn()
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: (
          <ReleasePicker
            workspaceId="ws-1"
            problem={problem}
            onCancel={onCancel}
          />
        ),
      },
    ],
    '/problems/prob-1',
  )
  expect(await screen.findByRole('radio', { name: /v4.13/ })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Load more' }))
  expect(await screen.findByRole('radio', { name: /v4.14/ })).toBeVisible()
  fireEvent.change(
    screen.getByRole('textbox', { name: 'Filter loaded releases' }),
    { target: { value: 'v4.14' } },
  )
  expect(screen.queryByRole('radio', { name: /v4.13/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('radio', { name: /v4.14/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Link release' }))
  await waitFor(() =>
    expect(submitted).toEqual({ expected_version: 2, external_id: '102' }),
  )
  expect(onCancel).toHaveBeenCalledOnce()
})

test.each([
  [
    'connection_not_ready',
    'Connect GitHub in workspace settings to link a release.',
  ],
  [
    'release_access_missing',
    'The GitHub App installation needs Contents read access. Ask the installation owner to accept the new permission.',
  ],
  ['release_provider_unavailable', 'Could not load releases'],
])('explains %s', async (reason, message) => {
  stubApi({
    'GET /api/workspaces/ws-1/releases/': () =>
      json(
        { detail: 'Unavailable', reason },
        reason === 'release_provider_unavailable' ? 503 : 409,
      ),
  })
  renderWorkspaceRoutes(
    [
      {
        path: '/problems/prob-1',
        element: (
          <ReleasePicker
            workspaceId="ws-1"
            problem={problem}
            onCancel={() => {}}
          />
        ),
      },
    ],
    '/problems/prob-1',
  )
  expect(
    await screen.findByText((text) => text.includes(message)),
  ).toBeVisible()
})
