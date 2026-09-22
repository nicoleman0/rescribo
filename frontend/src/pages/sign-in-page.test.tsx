import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { SignInPage } from './sign-in-page'
import { expect, test, vi } from 'vitest'

test('keeps the email and shows a rejected sign-in inline', async () => {
  document.cookie = 'csrftoken=csrf-token'
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 204 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: 'Email or password is incorrect.',
          reason: 'invalid_credentials',
          field_errors: {},
        }),
        { status: 401 },
      ),
    )
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
  expect(screen.getByRole('textbox', { name: 'Email' })).toHaveValue(
    'user@example.test',
  )
  expect(fetchMock.mock.calls[1][1]).toMatchObject({
    headers: { 'X-CSRFToken': expect.any(String) },
  })
})
