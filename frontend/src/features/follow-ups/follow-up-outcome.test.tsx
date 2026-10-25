import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { FollowUpDetail } from '@/api/follow-ups'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import {
  ada,
  base,
  csrfPath,
  definitionOf,
  detail,
  grace,
  notification,
  routes,
  stubDetail,
} from './follow-up-detail.fixtures'
import { ContactSection } from './follow-up-outcome'

test.each(['/follow-ups/fu-1', '/follow-ups/fu-1/page'])(
  'shows customer contact before a message is prepared at %s',
  async (path) => {
    stubDetail()
    renderWorkspaceRoutes(routes, path)
    expect(
      await screen.findByRole('region', { name: 'Customer contact' }),
    ).toBeVisible()
    expect(
      screen.getByRole('combobox', { name: 'Record outcome' }),
    ).toBeVisible()
  },
)

test('records contact with no message prepared', async () => {
  const bodies: unknown[] = []
  document.cookie = 'csrftoken=csrf-token'
  let current = detail()
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(current),
    [`POST ${base}/outcome/`]: (_url, init) => {
      bodies.push(JSON.parse(String(init?.body)))
      current = detail({
        outcome: {
          state: 'contacted',
          note: '',
          at: '2026-09-20T10:00:01Z',
          by: ada,
        },
        version: 2,
      })
      return json(current)
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('combobox', { name: 'Record outcome' })
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  await waitFor(() => expect(bodies).toHaveLength(1))
  expect(await screen.findByText('Outcome: Contacted.')).toBeVisible()
  expect(bodies).toEqual([
    { state: 'contacted', note: '', expected_version: 1 },
  ])
  expect(definitionOf('Delivery')).toHaveTextContent('Not prepared')
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

type OutcomeState = FollowUpDetail['outcome']['state']

function outcomeDetail(state: OutcomeState, version: number) {
  return detail({
    notification: notification('sent'),
    outcome:
      state === 'pending'
        ? { state, note: '', at: null, by: null }
        : { state, note: '', at: '2026-09-20T10:00:01Z', by: ada },
    version,
  })
}

// A follow-up the stubbed API keeps between requests: each outcome request
// moves it to the requested state and the next version. Returns the bodies.
function stubOutcomes(state: OutcomeState, version: number) {
  document.cookie = 'csrftoken=csrf-token'
  let current = outcomeDetail(state, version)
  const bodies: Record<string, unknown>[] = []
  const reply = (_url: URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body)) as {
      state: OutcomeState
      expected_version: number
    }
    bodies.push(body)
    current = outcomeDetail(body.state, body.expected_version + 1)
    return json(current)
  }
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(current),
    [`POST ${base}/outcome/`]: reply,
    [`POST ${base}/outcome/correct/`]: reply,
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
  })
  return bodies
}

const outcomeSelect = () =>
  screen.getByRole('combobox', { name: 'Record outcome' })
const noteBox = () => screen.getByRole('textbox', { name: 'Note' })
const reasonBox = () => screen.getByRole('textbox', { name: 'Reason' })

test('records contact and then confirmation without a reload', async () => {
  const bodies = stubOutcomes('pending', 1)
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('combobox', { name: 'Record outcome' })
  fireEvent.change(noteBox(), { target: { value: 'Called Acme' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  expect(await screen.findByText('Outcome: Contacted.')).toBeVisible()
  expect(outcomeSelect()).toHaveValue('confirmed')
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  await waitFor(() => expect(bodies).toHaveLength(2))
  expect(bodies).toEqual([
    { state: 'contacted', note: 'Called Acme', expected_version: 1 },
    { state: 'confirmed', note: '', expected_version: 2 },
  ])
})

test('records an outcome after a correction back to pending', async () => {
  const bodies = stubOutcomes('confirmed', 2)
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('form', { name: 'Correct outcome' })
  fireEvent.change(reasonBox(), { target: { value: 'Recorded by mistake' } })
  fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
  expect(await screen.findByText('Outcome: Pending.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  await waitFor(() => expect(bodies).toHaveLength(2))
  expect(bodies[1]).toEqual({
    state: 'contacted',
    note: '',
    expected_version: 3,
  })
})

test('corrects an outcome twice without a reload', async () => {
  const bodies = stubOutcomes('confirmed', 2)
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('form', { name: 'Correct outcome' })
  const correctTo = () => screen.getByRole('combobox', { name: 'Correct to' })
  fireEvent.change(correctTo(), { target: { value: 'still_affected' } })
  fireEvent.change(noteBox(), { target: { value: 'Export still fails' } })
  fireEvent.change(reasonBox(), { target: { value: 'First reason' } })
  fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
  expect(await screen.findByText('Outcome: Still affected.')).toBeVisible()
  expect(correctTo()).toHaveValue('pending')
  expect(reasonBox()).toHaveValue('')
  fireEvent.change(reasonBox(), { target: { value: 'Second reason' } })
  fireEvent.click(screen.getByRole('button', { name: 'Correct outcome' }))
  await waitFor(() => expect(bodies).toHaveLength(2))
  expect(bodies[1]).toEqual({
    state: 'pending',
    note: '',
    reason: 'Second reason',
    expected_version: 3,
  })
})

test('keeps the note when another member changed the outcome first', async () => {
  document.cookie = 'csrftoken=csrf-token'
  let current = outcomeDetail('pending', 1)
  const bodies: Record<string, unknown>[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(current),
    [`POST ${base}/outcome/`]: (_url, init) => {
      bodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
      if (bodies.length === 1) {
        // Another member recorded contact first.
        current = outcomeDetail('contacted', 2)
        return json(
          {
            detail: 'The follow-up changed.',
            reason: 'version_conflict',
            current,
          },
          409,
        )
      }
      current = outcomeDetail('confirmed', 3)
      return json(current)
    },
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await screen.findByRole('combobox', { name: 'Record outcome' })
  fireEvent.change(outcomeSelect(), { target: { value: 'contacted' } })
  fireEvent.change(noteBox(), { target: { value: 'Left a voicemail' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  expect(await screen.findByText('Outcome: Contacted.')).toBeVisible()
  expect(screen.getByText('The outcome was not recorded')).toBeVisible()
  expect(outcomeSelect()).toHaveValue('confirmed')
  expect(noteBox()).toHaveValue('Left a voicemail')
  fireEvent.click(screen.getByRole('button', { name: 'Record outcome' }))
  await waitFor(() => expect(bodies).toHaveLength(2))
  expect(bodies[1]).toEqual({
    state: 'confirmed',
    note: 'Left a voicemail',
    expected_version: 2,
  })
})

const mayNotRecord =
  "Only an owner, the report's assignee, or its submitter can record customer contact."

// A member who is not an owner, so the owner correction form never shows.
function renderContactForMember(followUp: FollowUpDetail) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ContactSection workspaceId="ws-1" followUp={followUp} isOwner={false} />
    </QueryClientProvider>,
  )
}

test.each(['pending', 'contacted'] as const)(
  'shows who can record instead of the form to other members at %s',
  (state) => {
    renderContactForMember({
      ...outcomeDetail(state, 1),
      can_record_outcome: false,
    })
    expect(screen.getByText(mayNotRecord)).toBeVisible()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  },
)

test('shows no form or line to other members once the outcome is final', () => {
  renderContactForMember({
    ...outcomeDetail('confirmed', 2),
    can_record_outcome: false,
  })
  expect(screen.getByText('Outcome: Confirmed.')).toBeVisible()
  expect(screen.queryByText(mayNotRecord)).not.toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('shows the form and no line to members who may record', async () => {
  stubDetail({ can_record_outcome: true })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  expect(
    await screen.findByRole('combobox', { name: 'Record outcome' }),
  ).toBeVisible()
  expect(screen.queryByText(mayNotRecord)).not.toBeInTheDocument()
})

test('replaces the form with the line when a stale page is refused', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const bodies: unknown[] = []
  let current = outcomeDetail('pending', 1)
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(current),
    [`POST ${base}/outcome/`]: (_url, init) => {
      bodies.push(JSON.parse(String(init?.body)))
      // The member lost the right to record after the page loaded.
      current = { ...outcomeDetail('pending', 1), can_record_outcome: false }
      return json(
        {
          detail: 'This action is not available.',
          reason: 'invalid_transition',
          current,
        },
        409,
      )
    },
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  fireEvent.click(await screen.findByRole('button', { name: 'Record outcome' }))
  expect(await screen.findByText(mayNotRecord)).toBeVisible()
  expect(bodies).toHaveLength(1)
  expect(
    screen.queryByRole('combobox', { name: 'Record outcome' }),
  ).not.toBeInTheDocument()
})
