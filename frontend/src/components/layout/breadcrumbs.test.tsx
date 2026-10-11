import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { expect, test } from 'vitest'
import { Breadcrumbs } from './breadcrumbs'

test.each([
  ['/inbox', 'Inbox'],
  ['/inbox/new', 'New report'],
  ['/problems', 'Problems'],
  ['/follow-ups', 'Follow-ups'],
  ['/settings', 'Settings'],
  ['/dev/ui', 'UI gallery'],
])('shows the current section for %s', (path, label) => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <Breadcrumbs />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  expect(
    screen.getByRole('navigation', { name: 'Breadcrumb' }),
  ).toBeInTheDocument()
  expect(screen.getByText(label)).toHaveAttribute('aria-current', 'page')
})
