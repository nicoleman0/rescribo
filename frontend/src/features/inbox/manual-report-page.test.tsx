import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
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
    await screen.findByText('The report was not created'),
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
    title: 'Export fails',
    description: '',
    customer_label: 'Acme',
    customer_contact_reference: '',
    affected_version: '',
  })
  expect(init?.headers).toMatchObject({ 'X-CSRFToken': 'csrf-token' })
  expect(sessionStorage.length).toBe(0)
})
