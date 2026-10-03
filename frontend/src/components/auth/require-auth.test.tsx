import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { RequireAuth } from './require-auth'

function Location() {
  return <p>{useLocation().pathname}</p>
}

function renderAuth() {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={['/inbox']}>
        <Routes>
          <Route element={<RequireAuth />}>
            <Route path="/inbox" element={<p>Protected content</p>} />
          </Route>
          <Route path="/sign-in" element={<Location />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('keeps the route and offers retry after a session transport failure', async () => {
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new Error('Network unavailable'))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          memberships: [
            {
              membership_id: 'm1',
              role: 'member',
              workspace: { id: 'w1', name: 'Workspace', slug: 'workspace' },
            },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  renderAuth()

  expect(await screen.findByText('Could not check your session')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  expect(await screen.findByText('Protected content')).toBeVisible()
  vi.unstubAllGlobals()
})

test('redirects only an explicit unauthenticated response', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('{}', { status: 401 })),
  )
  renderAuth()
  expect(await screen.findByText('/sign-in')).toBeVisible()
  vi.unstubAllGlobals()
})
