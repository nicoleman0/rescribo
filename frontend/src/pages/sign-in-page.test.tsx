import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { SignInPage } from './sign-in-page'
import { expect, test, vi } from 'vitest'

test('keeps the email and shows a rejected sign-in inline', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/auth/demo/'))
      return Promise.resolve(
        new Response(JSON.stringify({ credentials: null }), { status: 200 }),
      )
    if (url.includes('/auth/csrf/'))
      return Promise.resolve(new Response(null, { status: 204 }))
    if (url.includes('/auth/login/'))
      return Promise.resolve(
        new Response(
          JSON.stringify({
            detail: 'Email or password is incorrect.',
            reason: 'invalid_credentials',
            field_errors: {},
          }),
          { status: 401 },
        ),
      )
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SignInPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  fireEvent.change(screen.getByRole('textbox', { name: 'Email' }), {
    target: { value: 'user@example.test' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'bad-password' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Email or password is incorrect.',
    ),
  )
  expect(screen.queryByRole('button', { name: 'Use demo login' })).toBeNull()
  expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue(
    'user@example.test',
  )
  expect(
    fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/auth/login/'),
    )?.[1],
  ).toMatchObject({
    headers: { 'X-CSRFToken': expect.any(String) },
  })
})

test('fills and focuses the sign-in form from the demo hint', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      if (String(input).includes('/auth/demo/'))
        return Promise.resolve(
          new Response(
            JSON.stringify({
              credentials: {
                email: 'demo@example.com',
                password: 'Demo-password-42!',
              },
            }),
            { status: 200 },
          ),
        )
      throw new Error(`Unexpected request: ${String(input)}`)
    }),
  )
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SignInPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(await screen.findByText('demo@example.com')).toBeVisible()
  expect(screen.getByText('Demo-password-42!')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Use demo login' }))
  expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue(
    'demo@example.com',
  )
  expect(screen.getByLabelText('Password')).toHaveValue('Demo-password-42!')
  expect(screen.getByRole('button', { name: 'Sign in' })).toHaveFocus()
  vi.unstubAllGlobals()
})

test('a failed demo offer read stays hidden and does not block sign-in', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/auth/demo/'))
      return Promise.resolve(new Response('{}', { status: 503 }))
    if (url.includes('/auth/csrf/'))
      return Promise.resolve(new Response(null, { status: 204 }))
    if (url.includes('/auth/login/'))
      return Promise.resolve(
        new Response(
          JSON.stringify({ detail: 'Rejected', reason: 'invalid_credentials' }),
          { status: 401 },
        ),
      )
    throw new Error(`Unexpected request: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <SignInPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes('/auth/demo/')),
    ).toBe(true),
  )
  expect(screen.queryByRole('button', { name: 'Use demo login' })).toBeNull()
  fireEvent.change(screen.getByRole('textbox', { name: 'Email' }), {
    target: { value: 'member@example.test' },
  })
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'some-password' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Rejected')
  expect(
    fetchMock.mock.calls.some(([url]) => String(url).includes('/auth/login/')),
  ).toBe(true)
  vi.unstubAllGlobals()
})
