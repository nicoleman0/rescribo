import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import {
  json,
  renderWorkspaceRoutes,
  stubApi,
  testMembership,
} from '@/test/render'
import {
  ada,
  base,
  csrfPath,
  definitionOf,
  detail,
  notification,
  routes,
  stubDetail,
} from './follow-up-detail.fixtures'

const messageRegion = () => screen.getByRole('region', { name: 'Message' })

test('says contact is recorded when no message was prepared', async () => {
  stubDetail({ outcome: { state: 'contacted', note: '', at: null, by: ada } })
  const { unmount } = renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  const message = await screen.findByRole('region', { name: 'Message' })
  expect(message).toHaveTextContent('Customer contact is already recorded')
  expect(
    within(message).getByRole('button', { name: 'Prepare message' }),
  ).toBeVisible()

  unmount()
  stubDetail()
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1/page')
  expect(
    await screen.findByRole('region', { name: 'Message' }),
  ).not.toHaveTextContent('Customer contact is already recorded')
})

test('shows the queued status and stops polling once sent', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('queued') })),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(await screen.findByText('Send in progress')).toBeInTheDocument()
})

test('shows a delivered message with a confirmation when the recipient confirmed by hand', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          notification: notification('sent', 1, {
            delivery_confirmed_by: ada,
          }),
        }),
      ),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(await screen.findByText('Message sent')).toBeInTheDocument()
  expect(messageRegion()).toHaveTextContent(
    'Delivery confirmed by Ada Lovelace',
  )
  expect(
    screen.getByText('The fix for "CSV export fails" is available.'),
  ).toHaveClass('min-w-0', '[overflow-wrap:anywhere]')
})

test('shows Retry when the send failed', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: Record<string, unknown>[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          notification: notification('failed', 1, { safe_error: 'No token' }),
        }),
      ),
    [`POST ${base}/notification/approve/`]: (_url, init) => {
      sent.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
      return json(detail({ notification: notification('queued') }), 202)
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(await screen.findByText('No token')).toHaveClass(
    'min-w-0',
    '[overflow-wrap:anywhere]',
  )
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Retry sending' })).toBeEnabled(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Retry sending' }))
  await waitFor(() =>
    expect(sent).toEqual([{ notification_id: 'op-1', draft_version: 1 }]),
  )
})

test('offers mark delivered, send again with confirmation, and cancel for uncertain', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: { path: string; body: Record<string, unknown> }[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          notification: notification('uncertain', 1, {
            safe_error: 'Check the delivery log',
          }),
        }),
      ),
    [`POST ${base}/notification/mark-delivered/`]: (_url, init) => {
      sent.push({
        path: 'mark',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(detail({ notification: notification('sent') }))
    },
    [`POST ${base}/notification/send-again/`]: (_url, init) => {
      sent.push({
        path: 'send-again',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(detail({ notification: notification('queued') }), 202)
    },
    [`POST ${base}/notification/cancel/`]: (_url, init) => {
      sent.push({
        path: 'cancel',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(
        detail({
          notification: notification('cancelled', 1, {
            invalidated_at: '2026-09-20T10:00:05Z',
          }),
        }),
      )
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(await screen.findByText('Send uncertain')).toBeInTheDocument()
  expect(await screen.findByText('Check the delivery log')).toHaveClass(
    'min-w-0',
    '[overflow-wrap:anywhere]',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Mark as delivered' }))
  await waitFor(() => expect(sent.at(0)?.path).toBe('mark'))
  fireEvent.click(screen.getByRole('button', { name: 'Send again' }))
  expect(await screen.findByText('I checked Slack')).toBeInTheDocument()
  expect(
    screen.getByText(/the employee does not get a duplicate/),
  ).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByText('I checked Slack')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Send again' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Send again' }))
  await waitFor(() => expect(sent.at(-1)?.path).toBe('send-again'))
  expect(sent.at(-1)?.body).toEqual({
    notification_id: 'op-1',
    draft_version: 1,
    checked_slack: true,
  })
})

test('labels a delivered message in the demo as simulated', async () => {
  testMembership.workspace.is_demo = true
  try {
    stubApi({
      [csrfPath]: () => new Response(null, { status: 204 }),
      [`GET ${base}/`]: () =>
        json(detail({ notification: notification('sent') })),
    })
    renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
    expect(
      await screen.findByText('Message sent (simulated)'),
    ).toBeInTheDocument()
    expect(definitionOf('Delivery')).toHaveTextContent('Sent (simulated)')
    expect(messageRegion()).toHaveTextContent('No Slack message was sent.')
  } finally {
    testMembership.workspace.is_demo = false
  }
})
