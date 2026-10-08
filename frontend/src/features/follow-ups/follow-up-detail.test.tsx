import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { FollowUpDetail } from '@/api/follow-ups'
import {
  json,
  renderWorkspaceRoutes,
  stubApi,
  testMembership,
} from '@/test/render'
import { FollowUpDetailPanel } from './follow-up-detail'

const base = '/api/workspaces/ws-1/follow-ups/fu-1'
const csrfPath = 'GET /api/auth/csrf/'

const ada = { id: 'mem-2', display_name: 'Ada Lovelace' }
const grace = { id: 'mem-3', display_name: 'Grace Hopper' }

const routes = [
  {
    path: 'follow-ups/:followUpId',
    element: <FollowUpDetailPanel workspaceId="ws-1" followUpId="fu-1" />,
  },
]

function notification(
  state: 'draft' | 'queued' | 'failed' | 'uncertain' | 'sent' | 'cancelled',
  draftVersion = 1,
  overrides: Partial<FollowUpDetail['notification']> = {},
): NonNullable<FollowUpDetail['notification']> {
  return {
    id: 'op-1',
    send_in_progress: false,
    state,
    message: 'The fix for "CSV export fails" is available.',
    draft_version: draftVersion,
    safe_error: '',
    attempts: 1,
    approved_by: null,
    approved_at: null,
    sent_at: null,
    delivery_confirmed_by: null,
    delivery_confirmed_at: null,
    invalidated_at: null,
    invalidation_reason: '',
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-20T10:00:00Z',
    ...overrides,
  }
}

function detail(overrides: Partial<FollowUpDetail> = {}): FollowUpDetail {
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
    recipient: { member: ada, has_slack_link: true },
    notification: null,
    outcome: { state: 'pending', note: '', at: null, by: null },
    version: 1,
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-20T10:00:00Z',
    history: [],
    ...overrides,
  }
}

function stubDetail(overrides: Partial<FollowUpDetail> = {}) {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail(overrides)),
  })
}

const messageRegion = () => screen.getByRole('region', { name: 'Message' })

const definitionOf = (term: string) =>
  screen.getAllByRole('term').find((dt) => dt.textContent === term)
    ?.nextElementSibling

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
})

test('shows delivery as not prepared before a message exists', async () => {
  stubDetail()
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('heading', { name: 'CSV export fails' })
  expect(definitionOf('Delivery')).toHaveTextContent('Not prepared')
})

test('drafts the default message then edits it before approving', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const editBodies: string[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('draft') })),
    [`POST ${base}/notification/edit/`]: (_url, init) => {
      editBodies.push(String(init?.body))
      return json(detail({ notification: notification('draft', 2) }), 200)
    },
    [`POST ${base}/notification/approve/`]: () =>
      json(detail({ notification: notification('queued', 2) }), 202),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(
    (await screen.findAllByDisplayValue(/CSV export fails/)).length,
  ).toBeGreaterThan(0)
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
    target: { value: 'Edited message' },
  })
  expect(screen.getByRole('button', { name: 'Send to Slack' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Save edits' }))
  await waitFor(() => expect(editBodies).toHaveLength(1))
  expect(JSON.parse(editBodies[0])).toEqual({
    message: 'Edited message',
    notification_id: 'op-1',
    draft_version: 1,
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send to Slack' }))
})

test('keeps an edited draft on the page when the edit fails', async () => {
  document.cookie = 'csrftoken=csrf-token'
  let approveCalls = 0
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('draft') })),
    [`POST ${base}/notification/edit/`]: () =>
      json({ detail: 'The draft changed', reason: 'version_conflict' }, 409),
    [`POST ${base}/notification/approve/`]: () => {
      approveCalls += 1
      return json(detail(), 202)
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByText('Save edits')
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
    target: { value: 'My edit' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save edits' }))
  expect(
    await screen.findByText('The message was not saved'),
  ).toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: 'Message' })).toHaveValue(
    'My edit',
  )
  expect(screen.getByRole('button', { name: 'Send to Slack' })).toBeDisabled()
  expect(approveCalls).toBe(0)
})

test('keeps approval disabled while the edit is saving', async () => {
  document.cookie = 'csrftoken=csrf-token'
  let releaseSave: (() => void) | undefined
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('draft') })),
    [`POST ${base}/notification/edit/`]: () =>
      new Promise<Response>((resolve) => {
        releaseSave = () =>
          resolve(
            json(
              detail({
                notification: notification('draft', 2, {
                  message: 'Pending save',
                }),
              }),
            ),
          )
      }),
    [`POST ${base}/notification/approve/`]: () => json(detail(), 202),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('button', { name: 'Save edits' })
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
    target: { value: 'Pending save' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Save edits' }))
  expect(screen.getByRole('button', { name: 'Send to Slack' })).toBeDisabled()
  await waitFor(() => expect(releaseSave).toBeDefined())
  releaseSave?.()
  expect(screen.getByRole('button', { name: 'Send to Slack' })).toBeDisabled()
})

test('queues the send when a member clicks Send to Slack', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: Record<string, unknown>[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('draft') })),
    [`POST ${base}/notification/approve/`]: (_url, init) => {
      sent.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
      return json(detail({ notification: notification('queued') }), 202)
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Send to Slack' }))
  await waitFor(() =>
    expect(sent).toEqual([{ notification_id: 'op-1', draft_version: 1 }]),
  )
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
  expect(await screen.findByText('No token')).toBeInTheDocument()
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
      json(detail({ notification: notification('uncertain') })),
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
  fireEvent.click(screen.getByRole('button', { name: 'Mark as delivered' }))
  await waitFor(() => expect(sent.at(0)?.path).toBe('mark'))
  fireEvent.click(screen.getByRole('button', { name: 'Send again' }))
  expect(await screen.findByText('I checked Slack')).toBeInTheDocument()
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

test('offers copy-to-clipboard when the recipient has no Slack link', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          recipient: { member: ada, has_slack_link: false },
          notification: notification('draft'),
        }),
      ),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(
    await screen.findByRole('button', { name: 'Copy message' }),
  ).toBeInTheDocument()
  expect(
    screen.queryByRole('button', { name: 'Send to Slack' }),
  ).not.toBeInTheDocument()
})

test('records an outcome and requires a note for no response', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: { path: string; body: Record<string, unknown> }[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('sent') })),
    [`POST ${base}/outcome/`]: (_url, init) => {
      sent.push({
        path: 'outcome',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(
        detail({
          notification: notification('sent'),
          outcome: {
            state: 'contacted',
            note: '',
            at: '2026-09-20T10:00:01Z',
            by: ada,
          },
        }),
      )
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Record outcome' }))
  await waitFor(() => expect(sent.at(-1)?.path).toBe('outcome'))
  expect(sent.at(-1)?.body).toEqual({
    state: 'contacted',
    note: '',
    expected_version: 1,
  })
})

test('disables the submit button until a note is provided for no response', async () => {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ notification: notification('sent') })),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('combobox', { name: 'Record outcome' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Record outcome' }), {
    target: { value: 'no_response' },
  })
  expect(screen.getByRole('button', { name: 'Record outcome' })).toBeDisabled()
})

test('offers correction to an owner for a terminal outcome', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: { path: string; body: Record<string, unknown> }[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          notification: notification('sent'),
          outcome: {
            state: 'confirmed',
            note: '',
            at: '2026-09-20T10:00:01Z',
            by: ada,
          },
          version: 2,
        }),
      ),
    [`POST ${base}/outcome/correct/`]: (_url, init) => {
      sent.push({
        path: 'correct',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(
        detail({
          notification: notification('sent'),
          outcome: {
            state: 'pending',
            note: '',
            at: '2026-09-20T10:00:02Z',
            by: ada,
          },
          version: 3,
        }),
      )
    },
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('form', { name: 'Correct outcome' })
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason' }), {
    target: { value: 'Customer clarified the outcome' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
  await waitFor(() => expect(sent.at(-1)?.path).toBe('correct'))
  expect(sent.at(-1)?.body).toEqual({
    state: 'pending',
    note: '',
    reason: 'Customer clarified the outcome',
    expected_version: 2,
  })
})

test('blocks an owner correction that omits a reason', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(
        detail({
          notification: notification('sent'),
          outcome: {
            state: 'confirmed',
            note: '',
            at: '2026-09-20T10:00:01Z',
            by: ada,
          },
        }),
      ),
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('form', { name: 'Correct outcome' })
  fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
  expect(screen.getByRole('button', { name: 'Correct outcome' })).toBeDisabled()
})

test('lets an owner change the recipient', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const sent: { path: string; body: Record<string, unknown> }[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail()),
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
    [`POST ${base}/recipient/`]: (_url, init) => {
      sent.push({
        path: 'recipient',
        body: JSON.parse(String(init?.body)) as Record<string, unknown>,
      })
      return json(
        detail({ recipient: { member: grace, has_slack_link: true } }),
      )
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('option', { name: 'Ada Lovelace' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Recipient' }), {
    target: { value: grace.id },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Change recipient' }))
  await waitFor(() => expect(sent.at(-1)?.path).toBe('recipient'))
  expect(sent.at(-1)?.body).toEqual({ new_recipient_id: grace.id })
})

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
