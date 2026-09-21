import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  QueryState,
} from './async-states'

test('renders the shared loading state accessibly', () => {
  render(<LoadingState label="Loading inbox" />)
  expect(screen.getByRole('status', { name: 'Loading inbox' })).toHaveAttribute(
    'aria-busy',
    'true',
  )
})

test('renders an empty state with its action', () => {
  render(
    <EmptyState
      title="No reports"
      description="Reports will appear here."
      action={<button type="button">Connect source</button>}
    />,
  )
  expect(
    screen.getByRole('heading', { name: 'No reports' }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('button', { name: 'Connect source' }),
  ).toBeInTheDocument()
})

test('renders an error with a retry action', async () => {
  const onRetry = vi.fn()
  render(<ErrorState onRetry={onRetry} />)
  screen.getByRole('button', { name: 'Try again' }).click()
  expect(onRetry).toHaveBeenCalledOnce()
})

test('uses the same state pattern for query screens', () => {
  render(
    <QueryState status="ready">
      <p>Loaded result</p>
    </QueryState>,
  )
  expect(screen.getByText('Loaded result')).toBeInTheDocument()
})
