import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, test, vi } from 'vitest'
import { AcceptInvitePage } from './accept-invite-page'
import { ResetPasswordPage } from './reset-password-page'

test.each([
  [
    '/invite/:token',
    '/invite/example',
    <AcceptInvitePage key="invite" />,
    'Invite failed',
  ],
  [
    '/reset-password/:token',
    '/reset-password/example',
    <ResetPasswordPage key="reset" />,
    'Reset failed',
  ],
])(
  'shows a preview alert for %s failure',
  async (route, path, page, message) => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error(message)))
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route key={route} path={route} element={page} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(message),
    )
    vi.unstubAllGlobals()
  },
)
