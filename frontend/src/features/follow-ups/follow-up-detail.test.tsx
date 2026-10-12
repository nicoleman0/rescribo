import { screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { renderWorkspaceRoutes } from '@/test/render'
import {
  definitionOf,
  notification,
  routes,
  stubDetail,
} from './follow-up-detail.fixtures'

test('labels delivery and outcome and lists the follow-up details', async () => {
  stubDetail({
    notification: notification('failed'),
    outcome: {
      state: 'still_affected',
      note: 'Still slow',
      at: null,
      by: null,
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('heading', { name: 'CSV export fails' })
  expect(definitionOf('Delivery')).toHaveTextContent('Failed')
  expect(screen.getByText('Failed')).toHaveAttribute('data-tone', 'danger')
  expect(definitionOf('Outcome')).toHaveTextContent('Still affected')
  expect(definitionOf('Customer')).toHaveTextContent('Acme')
  expect(definitionOf('Fix')).toHaveTextContent('Fix the parser')
  expect(definitionOf('Available in')).toHaveTextContent('1.0')
  expect(definitionOf('Destination')).toHaveTextContent(
    'Slack DM to Ada Lovelace',
  )
  expect(definitionOf('Outcome note')).toHaveTextContent('Still slow')
  for (const note of screen.getAllByText('Still slow')) {
    expect(note).toHaveClass('min-w-0', '[overflow-wrap:anywhere]')
  }
})

test('shows delivery as not prepared before a message exists', async () => {
  stubDetail()
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('heading', { name: 'CSV export fails' })
  expect(definitionOf('Delivery')).toHaveTextContent('Not prepared')
  expect(
    screen.getByRole('heading', { name: 'Message to the employee' }),
  ).toBeInTheDocument()
})

test('uses page heading levels and page section layout', async () => {
  stubDetail({
    notification: notification('sent'),
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
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1/page')
  expect(
    await screen.findByRole('heading', { name: 'CSV export fails', level: 1 }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Message sent', level: 2 }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'History', level: 2 }),
  ).toBeInTheDocument()
  expect(screen.getByRole('region', { name: 'Message' })).toHaveClass('bg-card')
})

test('links from the panel to the full page with the current query', async () => {
  stubDetail()
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1?bucket=needs_approval&page=2')
  expect(
    await screen.findByRole('link', { name: 'Open full page' }),
  ).toHaveAttribute(
    'href',
    '/follow-ups/fu-1/page?bucket=needs_approval&page=2',
  )
})
