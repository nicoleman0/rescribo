import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test } from 'vitest'
import { stubPickerDom } from '@/components/member-picker/test-support'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import {
  ada,
  base,
  csrfPath,
  detail,
  grace,
  routes,
} from './follow-up-detail.fixtures'

beforeEach(stubPickerDom)

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
  await userEvent.click(
    await screen.findByRole('combobox', { name: 'Recipient: Ada Lovelace' }),
  )
  await userEvent.click(
    await screen.findByRole('option', { name: 'Grace Hopper' }),
  )
  await waitFor(() => expect(sent.at(-1)?.path).toBe('recipient'))
  expect(sent.at(-1)?.body).toEqual({ new_recipient_id: grace.id })
})

test('shows unlinked recipients disabled and keeps an unlinked current recipient enabled', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () =>
      json(detail({ recipient: { member: ada, has_slack_link: false } })),
    'GET /api/workspaces/ws-1/members/': () =>
      json([{ ...ada, has_slack_link: false }, grace]),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await userEvent.click(
    await screen.findByRole('combobox', { name: 'Recipient: Ada Lovelace' }),
  )
  const current = await screen.findByRole('option', {
    name: 'Ada Lovelace (no Slack link)',
  })
  expect(current).not.toHaveAttribute('aria-disabled', 'true')
  expect(
    screen.getByRole('option', { name: 'Grace Hopper' }),
  ).not.toHaveAttribute('aria-disabled', 'true')
})

test('shows the server reason and refetches members after a recipient refusal', async () => {
  document.cookie = 'csrftoken=csrf-token'
  let directoryReads = 0
  const detailText =
    'This member has not linked a Slack account. Choose a member with a Slack link, or ask this member to link Slack in Settings.'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail()),
    'GET /api/workspaces/ws-1/members/': () => {
      directoryReads += 1
      return json([ada, grace])
    },
    [`POST ${base}/recipient/`]: () =>
      json(
        {
          detail: detailText,
          reason: 'recipient_not_linked',
          field_errors: {},
        },
        400,
      ),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await userEvent.click(
    await screen.findByRole('combobox', { name: 'Recipient: Ada Lovelace' }),
  )
  await userEvent.click(
    await screen.findByRole('option', { name: 'Grace Hopper' }),
  )
  // The message shows inside the open picker.
  expect(await screen.findByText(detailText)).toBeVisible()
  expect(screen.getByText('The recipient was not changed')).toBeInTheDocument()
  expect(screen.getByRole('listbox')).toBeInTheDocument()
  await waitFor(() => expect(directoryReads).toBeGreaterThan(1))
})

test('shows an invalid recipient in the picker', async () => {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail()),
    'GET /api/workspaces/ws-1/members/': () => json([ada, grace]),
    [`POST ${base}/recipient/`]: () =>
      json(
        {
          detail: 'Choose an existing, active record in this workspace.',
          reason: 'invalid_reference',
          field_errors: { new_recipient_id: ['invalid_reference'] },
        },
        400,
      ),
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  await userEvent.click(
    await screen.findByRole('combobox', { name: 'Recipient: Ada Lovelace' }),
  )
  await userEvent.click(
    await screen.findByRole('option', { name: 'Grace Hopper' }),
  )
  expect(
    await screen.findByText('Choose an active record in this workspace.'),
  ).toBeInTheDocument()
})
