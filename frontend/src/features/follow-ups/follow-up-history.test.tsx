import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import {
  ada,
  base,
  csrfPath,
  detail,
  routes,
  stubDetail,
} from './follow-up-detail.fixtures'

test('renders the history feed', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          history: [
            {
              id: 'act-1',
              action: 'follow_up.notification_approved',
              actor: ada,
              actor_system: '',
              created_at: '2026-09-20T10:00:01Z',
            },
            {
              id: 'act-2',
              action: 'follow_up.notification_sent',
              actor: null,
              actor_system: 'celery',
              created_at: '2026-09-20T10:00:02Z',
            },
          ],
        }),
      ),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(
    await screen.findByText('approved the message for sending'),
  ).toBeInTheDocument()
  expect(screen.getByText('recorded the send')).toBeInTheDocument()
})

test('uses section-level headings for panel history', async () => {
  stubDetail({
    history: [
      {
        id: 'act-1',
        action: 'follow_up.notification_sent',
        actor: null,
        actor_system: 'celery',
        created_at: '2026-09-20T10:00:02Z',
      },
    ],
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(
    await screen.findByRole('heading', { name: 'History', level: 3 }),
  ).toBeInTheDocument()
})
