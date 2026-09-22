import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { AppShell } from './app-shell'

test('exposes all primary destinations from the shell', () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={['/inbox']}>
        <AppShell>
          <h1>Inbox</h1>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  )

  expect(screen.getAllByRole('link', { name: 'Inbox' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Problems' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Follow-ups' })).toHaveLength(2)
  expect(screen.getAllByRole('link', { name: 'Settings' })).toHaveLength(2)
})
