import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import App from './App'

function renderApp() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
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
