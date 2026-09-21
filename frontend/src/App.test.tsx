import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { DevelopmentStatusPage } from './pages/development-status-page'

function renderApp() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DevelopmentStatusPage />
    </QueryClientProvider>,
  )
}

test('shows successful service readiness', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }),
  )
  renderApp()
  expect(
    await screen.findByText('API, PostgreSQL, and Redis are ready.'),
  ).toBeInTheDocument()
})

test('shows an actionable error when the API is down', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
  renderApp()
  expect(await screen.findByText(/Services unavailable/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Check again' })).toBeEnabled()
})
