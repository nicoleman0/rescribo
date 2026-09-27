import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import { json, renderWorkspaceRoutes, stubApi } from '@/test/render'
import { ManualReportPage } from './manual-report-page'

const routes = [
  { path: '/inbox/new', element: <ManualReportPage /> },
  { path: '/inbox/:reportId', element: <p>Report page</p> },
]
const createPath = 'POST /api/workspaces/ws-1/reports/'
const csrfPath = 'GET /api/auth/csrf/'

afterEach(() => sessionStorage.clear())

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

test('keeps the draft and shows field errors when creation fails', async () => {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: () =>
      json(
        {
          detail: 'Check the submitted fields.',
          reason: 'invalid_request',
          field_errors: { affected_version: ['Too long.'] },
        },
        400,
      ),
  })
  const view = renderWorkspaceRoutes(routes, '/inbox/new')
  fill('Title', 'Export fails')
  fill('Description', 'Stops at 50%')
  fill('Affected version', '9.9.9')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  expect(
    await screen.findByText('Could not confirm report creation'),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Affected version')).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  expect(screen.getByText('Too long.')).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Export fails')
  expect(screen.getByLabelText('Description')).toHaveValue('Stops at 50%')

  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox/new')
  expect(screen.getByText('Restored your unsaved draft')).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Export fails')
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }))
  expect(screen.getByLabelText('Title')).toHaveValue('')
  expect(sessionStorage.length).toBe(0)
})

test('explains a network failure without losing the draft', async () => {
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: () => {
      throw new TypeError('Failed to fetch')
    },
  })
  renderWorkspaceRoutes(routes, '/inbox/new')
  fill('Title', 'Offline report')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  expect(
    await screen.findByText(/Could not reach Rescribo/),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toHaveValue('Offline report')
})

test('creates a manual report, clears the draft, and opens it', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const fetchMock = stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: () => json({ id: 'rep-9' }, 201),
  })
  renderWorkspaceRoutes(routes, '/inbox/new')
  fill('Title', 'Export fails')
  fill('Customer organisation', 'Acme')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  await waitFor(() =>
    expect(screen.getByTestId('location')).toHaveTextContent('/inbox/rep-9'),
  )
  const [, init] = fetchMock.mock.calls.at(-1)!
  expect(JSON.parse(String(init?.body))).toEqual({
    submission_key: expect.any(String),
    title: 'Export fails',
    description: '',
    customer_label: 'Acme',
    customer_contact_reference: '',
    affected_version: '',
  })
  expect(init?.headers).toMatchObject({ 'X-CSRFToken': 'csrf-token' })
  expect(sessionStorage.length).toBe(0)
})

test('locks the fields while the create request is pending', async () => {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: () => new Promise(() => {}),
  })
  renderWorkspaceRoutes(routes, '/inbox/new')
  fill('Title', 'Pending report')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  expect(await screen.findByText('Creating report…')).toBeInTheDocument()
  expect(screen.getByLabelText('Title')).toBeDisabled()
})

const storageKey = 'rescribo:report-draft:ws-1'
const uuidPattern = /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i
const storedDraft = () =>
  JSON.parse(sessionStorage.getItem(storageKey)!) as {
    submission_key: string
    title: string
  }

test('reuses its persisted key through edits, failures and remounts, then clears a replay', async () => {
  const requests: { submission_key: string; title: string }[] = []
  let replay = false
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: (_url, init) => {
      const input = JSON.parse(String(init?.body))
      requests.push(input)
      expect(storedDraft()).toMatchObject(input)
      if (!replay) throw new TypeError('Response lost')
      return json({ id: 'rep-original' }, 200)
    },
  })
  let view = renderWorkspaceRoutes(routes, '/inbox/new')
  const key = storedDraft().submission_key
  expect(key).toMatch(uuidPattern)
  expect(
    screen.queryByText('Restored your unsaved draft'),
  ).not.toBeInTheDocument()
  fill('Title', 'First attempt')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  await screen.findByText('Could not confirm report creation')
  fill('Title', 'Edited retry')
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  await waitFor(() => expect(requests).toHaveLength(2))
  await screen.findByText('Could not confirm report creation')
  view.unmount()
  view = renderWorkspaceRoutes(routes, '/inbox/new')
  expect(screen.getByLabelText('Title')).toHaveValue('Edited retry')
  expect(storedDraft().submission_key).toBe(key)
  replay = true
  fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
  await screen.findByText('Report page')
  expect(requests.map((input) => input.submission_key)).toEqual([key, key, key])
  expect(sessionStorage.getItem(storageKey)).toBeNull()
  expect(screen.getByTestId('location')).toHaveTextContent(
    '/inbox/rep-original',
  )
  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox/new')
  expect(storedDraft().submission_key).not.toBe(key)
  expect(screen.getByLabelText('Title')).toHaveValue('')
})

test('upgrades legacy text once and uses a fresh identity after discard', () => {
  sessionStorage.setItem(
    storageKey,
    JSON.stringify({ title: 'Legacy title', description: 'Kept' }),
  )
  const view = renderWorkspaceRoutes(routes, '/inbox/new')
  expect(screen.getByLabelText('Title')).toHaveValue('Legacy title')
  expect(screen.getByLabelText('Description')).toHaveValue('Kept')
  const key = storedDraft().submission_key
  expect(key).toMatch(uuidPattern)
  view.unmount()
  renderWorkspaceRoutes(routes, '/inbox/new')
  expect(storedDraft().submission_key).toBe(key)
  fireEvent.click(screen.getByRole('button', { name: 'Discard draft' }))
  expect(sessionStorage.getItem(storageKey)).toBeNull()
  fill('Title', 'Next draft')
  expect(storedDraft().submission_key).toMatch(uuidPattern)
  expect(storedDraft().submission_key).not.toBe(key)
})

test.each([
  '{invalid',
  'null',
  '42',
  '[]',
  JSON.stringify({
    title: 'Recoverable text',
    description: {},
    submission_key: 'broken',
  }),
])('restores only valid fields and repairs invalid storage: %s', (stored) => {
  sessionStorage.setItem(storageKey, stored)
  renderWorkspaceRoutes(routes, '/inbox/new')
  expect(storedDraft().submission_key).toMatch(uuidPattern)
  expect(screen.getByLabelText('Description')).toHaveValue('')
  expect(screen.getByLabelText('Title')).toHaveValue(
    stored.includes('Recoverable') ? 'Recoverable text' : '',
  )
})

test('keeps a stable in-memory retry key when session storage is unavailable', async () => {
  const read = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('Blocked')
  })
  const write = vi
    .spyOn(Storage.prototype, 'setItem')
    .mockImplementation(() => {
      throw new Error('Blocked')
    })
  const remove = vi
    .spyOn(Storage.prototype, 'removeItem')
    .mockImplementation(() => {
      throw new Error('Blocked')
    })
  const keys: string[] = []
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [createPath]: (_url, init) => {
      keys.push(JSON.parse(String(init?.body)).submission_key)
      if (keys.length === 1) throw new TypeError('Offline')
      return json({ id: 'recovered' }, 200)
    },
  })
  try {
    renderWorkspaceRoutes(routes, '/inbox/new')
    fill('Title', 'Memory only')
    fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
    await screen.findByText('Could not confirm report creation')
    expect(screen.getByLabelText('Title')).toHaveValue('Memory only')
    fireEvent.click(screen.getByRole('button', { name: 'Create report' }))
    await screen.findByText('Report page')
    expect(keys[0]).toMatch(uuidPattern)
    expect(keys[1]).toBe(keys[0])
  } finally {
    read.mockRestore()
    write.mockRestore()
    remove.mockRestore()
  }
})

test('does not reuse another workspace draft or key', () => {
  const otherKey = 'rescribo:report-draft:ws-2'
  const other = JSON.stringify({
    title: 'Other workspace',
    submission_key: crypto.randomUUID(),
  })
  sessionStorage.setItem(otherKey, other)
  renderWorkspaceRoutes(routes, '/inbox/new')
  expect(screen.getByLabelText('Title')).toHaveValue('')
  fill('Title', 'This workspace')
  expect(storedDraft().submission_key).not.toBe(
    JSON.parse(other).submission_key,
  )
  expect(sessionStorage.getItem(otherKey)).toBe(other)
})
