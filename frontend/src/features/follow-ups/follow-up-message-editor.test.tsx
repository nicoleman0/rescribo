import { fireEvent, screen, waitFor } from '@testing-library/react'
import { expect, test } from 'vitest'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import {
  ada,
  base,
  csrfPath,
  detail,
  notification,
  routes,
} from './follow-up-detail.fixtures'

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
  const textbox = await screen.findByRole('textbox', { name: 'Message' })
  expect(
    screen.queryByRole('heading', { name: 'Message to the employee' }),
  ).not.toBeInTheDocument()
  expect(textbox).toHaveAccessibleDescription(
    'Edits are saved when you select Save edits. If a save fails, your text stays here.',
  )
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
