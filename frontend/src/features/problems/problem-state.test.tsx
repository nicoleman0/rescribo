import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { NeedsReviewBadge, ProblemStateBadge } from './problem-state'
import { problemStateLabels } from './problem-format'

test.each([
  ['open', 'info'],
  ['in_progress', 'progress'],
  ['fix_available', 'success'],
  ['not_planned', 'neutral'],
] as const)('shows a %s problem in the %s tone', (state, tone) => {
  render(<ProblemStateBadge state={state} />)
  expect(screen.getByText(problemStateLabels[state])).toHaveAttribute(
    'data-tone',
    tone,
  )
})

test('shows needs review as a warning', () => {
  render(<NeedsReviewBadge />)
  expect(screen.getByText('Needs review')).toHaveAttribute(
    'data-tone',
    'warning',
  )
})
