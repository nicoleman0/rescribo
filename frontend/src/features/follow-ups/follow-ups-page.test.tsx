import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { FollowUpListItem, FollowUpPage } from '@/api/follow-ups'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { FollowUpsPage } from './follow-ups-page'

const ada = { id: 'mem-2', display_name: 'Ada Lovelace' }

const item = (overrides: Partial<FollowUpListItem> = {}): FollowUpListItem => ({
  id: 'fu-1',
  report_title: 'CSV export fails',
  customer_label: 'Acme',
  recipient: ada,
  contact_state: 'pending',
  delivery_state: null,
  resolution_revision: 2,
  created_at: '2026-09-20T10:00:00Z',
  updated_at: '2026-09-20T10:00:00Z',
  ...overrides,
})

const page = (results: FollowUpListItem[], count?: number): FollowUpPage => ({
  count: count ?? results.length,
  next: null,
  previous: null,
  results,
})

const routes = [
  { path: 'follow-ups', element: <FollowUpsPage /> },
  { path: 'follow-ups/:followUpId', element: <FollowUpsPage /> },
]

const listKey = 'GET /api/workspaces/ws-1/follow-ups/'

/** stubApi keys handlers by pathname only, so bucket variants must be
 * dispatched inside one handler on the bucket query param. Values are
 * either a page or a per-call handler for the '/' (unfiltered) bucket. */
const listHandler =
  (
    byBucket: Record<string, FollowUpPage | ((url: URL) => Response)>,
  ): ((url: URL) => Response) =>
  (url) => {
    const bucket = url.searchParams.get('bucket') ?? ''
    const value = byBucket[bucket]
    if (typeof value === 'function') return value(url)
    return json(value)
  }

const detail: FollowUpListItem = item({ id: 'fu-1' })

const detailResponse = () =>
  json({
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
  })

test('lists follow-ups and switches buckets in the URL', async () => {
  stubApi({
    [listKey]: listHandler({
      '': page([item(), item({ id: 'fu-2' })]),
      needs_approval: page([item()], 1),
      delivery_problem: page([], 0),
      awaiting_contact: page([], 0),
      awaiting_confirmation: page([], 0),
      completed: page([], 0),
    }),
    'GET /api/workspaces/ws-1/follow-ups/fu-1/': detailResponse,
  })
  renderWorkspaceRoutes(routes, '/follow-ups')
  const list = await screen.findByRole('list', { name: 'Follow-ups' })
  expect(within(list).getAllByRole('link')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: /Needs approval/ }))
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent(
      'bucket=needs_approval',
    ),
  )
  await waitFor(() => {
    // The unfiltered list is replaced by the bucket's own page.
    const next = screen.getByRole('list', { name: 'Follow-ups' })
    expect(within(next).getAllByRole('link')).toHaveLength(1)
  })
  expect(screen.getByText('1 follow-up')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Awaiting contact/ }))
  await screen.findByText('Nothing awaiting contact')
  expect(screen.getByTestId('location')).toHaveTextContent(
    'bucket=awaiting_contact',
  )
})

test('paginates follow-ups, resets on bucket change, and supports keyboard navigation', async () => {
  stubApi({
    [listKey]: (url) => {
      const bucket = url.searchParams.get('bucket') ?? ''
      const currentPage = url.searchParams.get('page') ?? '1'
      if (bucket === 'needs_approval' && currentPage === '2') {
        return json(
          page([item({ id: 'fu-26', report_title: 'Page two report' })], 26),
        )
      }
      if (bucket === 'needs_approval') {
        return json(
          page(
            Array.from({ length: 25 }, (_, index) =>
              item({ id: `fu-${index + 1}` }),
            ),
            26,
          ),
        )
      }
      if (bucket === 'delivery_problem') {
        return json(
          page([item({ id: 'fu-d', report_title: 'Failed delivery' })], 1),
        )
      }
      return json(page([], 0))
    },
  })
  renderWorkspaceRoutes(routes, '/follow-ups?bucket=needs_approval')
  const next = await screen.findByRole('button', { name: 'Next page' })
  next.focus()
  fireEvent.keyDown(next, { key: 'Enter' })
  fireEvent.click(next)
  const secondPageLink = await screen.findByRole('link', {
    name: /Page two report/,
  })
  expect(secondPageLink).toHaveAttribute(
    'href',
    '/follow-ups/fu-26?bucket=needs_approval&page=2',
  )
  expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Delivery problem/ }))
  const bucketLink = await screen.findByRole('link', {
    name: /Failed delivery/,
  })
  expect(bucketLink).toHaveAttribute(
    'href',
    '/follow-ups/fu-d?bucket=delivery_problem',
  )
})

test('shows a per-bucket empty state when the bucket has nothing', async () => {
  stubApi({
    [listKey]: listHandler({
      '': page([], 0),
      needs_approval: page([], 0),
      delivery_problem: page([], 0),
      awaiting_contact: page([], 0),
      awaiting_confirmation: page([], 0),
      completed: page([], 0),
    }),
  })
  renderWorkspaceRoutes(routes, '/follow-ups?bucket=needs_approval')
  expect(
    await screen.findByText('No follow-ups waiting for approval'),
  ).toBeInTheDocument()
})

test('shows a generic empty state when the unfiltered list is empty', async () => {
  stubApi({
    [listKey]: listHandler({
      '': page([], 0),
      needs_approval: page([], 0),
      delivery_problem: page([], 0),
      awaiting_contact: page([], 0),
      awaiting_confirmation: page([], 0),
      completed: page([], 0),
    }),
  })
  renderWorkspaceRoutes(routes, '/follow-ups')
  expect(await screen.findByText('No follow-ups yet')).toBeInTheDocument()
})

test('replaces the list with an error state that supports retry', async () => {
  let listAttempts = 0
  stubApi({
    [listKey]: listHandler({
      '': () => {
        listAttempts += 1
        return listAttempts === 1
          ? json({ detail: 'Server error', reason: 'error' }, 500)
          : json(page([item()]))
      },
      needs_approval: page([item()]),
    }),
  })
  renderWorkspaceRoutes(routes, '/follow-ups')
  expect(
    await screen.findByText('Could not load follow-ups'),
  ).toBeInTheDocument()
  const listError = screen
    .getByText('Could not load follow-ups')
    .closest('[role="alert"]')
  expect(listError).not.toBeNull()
  fireEvent.click(
    within(listError as HTMLElement).getByRole('button', { name: 'Try again' }),
  )
  await screen.findByText('CSV export fails')
})

test('marks the selected follow-up and renders the detail', async () => {
  stubApi({
    [listKey]: listHandler({
      '': page([detail]),
      needs_approval: page([detail]),
    }),
    'GET /api/workspaces/ws-1/follow-ups/fu-1/': detailResponse,
  })
  renderWorkspaceRoutes(routes, '/follow-ups/fu-1')
  const link = await screen.findByRole('link', { name: /CSV export fails/ })
  expect(link).toHaveAttribute('aria-current', 'page')
  await screen.findByRole('region', { name: 'Follow-up detail' })
})

test('shows delivery and contact states in their status tones', async () => {
  stubApi({
    [listKey]: listHandler({
      '': page([
        item({ delivery_state: 'failed', contact_state: 'still_affected' }),
      ]),
    }),
  })
  renderWorkspaceRoutes(routes, '/follow-ups')
  const list = await screen.findByRole('list', { name: 'Follow-ups' })
  expect(within(list).getByText('Failed')).toHaveAttribute(
    'data-tone',
    'danger',
  )
  expect(within(list).getByText('Still affected')).toHaveAttribute(
    'data-tone',
    'warning',
  )
})
