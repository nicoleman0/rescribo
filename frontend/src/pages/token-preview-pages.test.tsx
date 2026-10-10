import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { AcceptInvitePage } from './accept-invite-page'
import { ResetPasswordPage } from './reset-password-page'

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

test.each([
  [
    '/invite/:token',
    '/invite/example',
    <AcceptInvitePage key="invite" />,
    'Password',
  ],
  [
    '/reset-password/:token',
    '/reset-password/example',
    <ResetPasswordPage key="reset-password" />,
    'New password',
  ],
])(
  'recovers a transient preview failure on %s',
  async (route, path, page, passwordLabel) => {
    let previews = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes('/auth/csrf/'))
          return Promise.resolve(new Response(null, { status: 204 }))
        previews += 1
        return Promise.resolve(
          previews === 1
            ? response({ detail: 'Temporary failure' }, 503)
            : response({ status: 'valid', workspace_name: 'Example' }),
        )
      }),
    )
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={route} element={page} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(/could not check this/i)).toBeVisible()
    const retry = screen.getByRole('button', { name: 'Try again' })
    expect(retry).toBeEnabled()
    await user.click(retry)
    expect(await screen.findByLabelText(passwordLabel)).toBeVisible()
    vi.unstubAllGlobals()
  },
)

function ChangeInviteToken() {
  const navigate = useNavigate()
  return (
    <button onClick={() => navigate('/invite/new-token')}>Change token</button>
  )
}

test('keeps a late preview result scoped to its invitation token', async () => {
  let finishOld!: (value: Response) => void
  const oldResult = new Promise<Response>((resolve) => {
    finishOld = resolve
  })
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/csrf/'))
        return Promise.resolve(new Response(null, { status: 204 }))
      if (url.includes('/invitations/preview/')) {
        const token = (JSON.parse(String(init?.body)) as { token: string })
          .token
        return token === 'old-token'
          ? oldResult
          : Promise.resolve(
              response({ status: 'valid', workspace_name: 'New workspace' }),
            )
      }
      throw new Error(`Unexpected request: ${url}`)
    }),
  )
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/invite/old-token']}>
        <Routes>
          <Route
            path="/invite/:token"
            element={
              <>
                <ChangeInviteToken />
                <AcceptInvitePage />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await user.click(screen.getByRole('button', { name: 'Change token' }))
  expect(await screen.findByText('Join New workspace.')).toBeVisible()
  finishOld(response({ status: 'valid', workspace_name: 'Old workspace' }))
  expect(screen.queryByText('Join Old workspace.')).not.toBeInTheDocument()
  vi.unstubAllGlobals()
})

test.each([
  [401, 'This email already has an account', 'Accept invitation'],
  [500, 'Could not check your session', 'Try again'],
])(
  'handles a %s session check on a requires_sign_in invitation',
  async (status, text, actionName) => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/auth/csrf/'))
          return Promise.resolve(new Response(null, { status: 204 }))
        if (url.includes('/invitations/preview/'))
          return Promise.resolve(response({ status: 'requires_sign_in' }))
        if (url.includes('/auth/session/'))
          return Promise.resolve(response({ detail: 'Nope' }, status))
        throw new Error(`Unexpected request: ${url}`)
      }),
    )
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/invite/example']}>
          <Routes>
            <Route path="/invite/:token" element={<AcceptInvitePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText(new RegExp(text))).toBeVisible()
    expect(screen.getByRole('button', { name: actionName })).toBeVisible()
    if (status === 401)
      expect(
        screen.queryByText('Could not check your session'),
      ).not.toBeInTheDocument()
    vi.unstubAllGlobals()
  },
)

test('an existing account accepts with its password', async () => {
  const bodies: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/csrf/'))
        return Promise.resolve(new Response(null, { status: 204 }))
      if (url.includes('/invitations/preview/'))
        return Promise.resolve(
          response({ status: 'requires_sign_in', workspace_name: 'Example' }),
        )
      if (url.includes('/auth/session/'))
        return Promise.resolve(response({ detail: 'Nope' }, 401))
      if (url.includes('/invitations/accept/')) {
        bodies.push(JSON.parse(String(init?.body)))
        return Promise.resolve(
          bodies.length === 1
            ? response(
                {
                  detail: 'Password is incorrect.',
                  reason: 'invalid_credentials',
                  field_errors: { password: ['Password is incorrect.'] },
                },
                401,
              )
            : response({
                user: { id: '1', email: 'back@example.test', full_name: 'B' },
                memberships: [],
              }),
        )
      }
      throw new Error(`Unexpected request: ${url}`)
    }),
  )
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/invite/example']}>
        <Routes>
          <Route path="/invite/:token" element={<AcceptInvitePage />} />
          <Route path="/inbox" element={<p>Inbox reached</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const password = await screen.findByLabelText('Password')
  expect(screen.getByText(/Join Example\./)).toBeVisible()
  expect(screen.queryByLabelText('Full name')).not.toBeInTheDocument()
  expect(
    screen.queryByRole('link', { name: 'Sign in' }),
  ).not.toBeInTheDocument()
  const submit = screen.getByRole('button', { name: 'Accept invitation' })
  await user.type(password, 'wrong-password')
  await user.click(submit)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Password is incorrect.',
  )
  expect(password).toHaveValue('wrong-password')
  await user.clear(password)
  await user.type(password, 'right-password')
  await user.click(submit)
  expect(await screen.findByText('Inbox reached')).toBeVisible()
  expect(bodies).toEqual([
    { token: 'example', full_name: '', password: 'wrong-password' },
    { token: 'example', full_name: '', password: 'right-password' },
  ])
  vi.unstubAllGlobals()
})

test('the reset page shows why a password was refused and keeps the form', async () => {
  const bodies: unknown[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/auth/csrf/'))
        return Promise.resolve(new Response(null, { status: 204 }))
      if (url.includes('/password-resets/preview/'))
        return Promise.resolve(response({ status: 'valid' }))
      if (url.includes('/password-resets/redeem/')) {
        bodies.push(JSON.parse(String(init?.body)))
        return Promise.resolve(
          bodies.length === 1
            ? response(
                {
                  detail: 'Choose a different password.',
                  reason: 'password_unchanged',
                  field_errors: {
                    password: ['This is your current password.'],
                  },
                },
                400,
              )
            : response({
                user: { id: '1', email: 'member@example.test', full_name: 'M' },
                memberships: [],
              }),
        )
      }
      throw new Error(`Unexpected request: ${url}`)
    }),
  )
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/reset-password/example']}>
        <Routes>
          <Route
            path="/reset-password/:token"
            element={<ResetPasswordPage />}
          />
          <Route path="/inbox" element={<p>Inbox reached</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const password = await screen.findByLabelText('New password')
  const confirm = screen.getByLabelText('Confirm password')
  const submit = screen.getByRole('button', { name: 'Save password' })
  await user.type(password, 'current-password')
  await user.type(confirm, 'current-password')
  await user.click(submit)
  expect(
    await screen.findByText('This is your current password.'),
  ).toBeVisible()
  expect(screen.getByText('Choose a different password.')).toBeVisible()
  expect(password).toHaveAccessibleDescription('This is your current password.')
  expect(password).toHaveValue('current-password')
  await user.clear(password)
  await user.type(password, 'another-password')
  await user.clear(confirm)
  await user.type(confirm, 'another-password')
  await user.click(submit)
  expect(await screen.findByText('Inbox reached')).toBeVisible()
  expect(bodies).toEqual([
    { token: 'example', password: 'current-password' },
    { token: 'example', password: 'another-password' },
  ])
  vi.unstubAllGlobals()
})
