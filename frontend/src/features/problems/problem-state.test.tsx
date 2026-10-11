import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import {
  NeedsReviewBadge,
  NoReportsBadge,
  ProblemStateBadge,
} from './problem-state'
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

test.each([
  ['open', 0, true],
  ['in_progress', 0, true],
  ['fix_available', 0, false],
  ['not_planned', 0, false],
  ['open', 1, false],
] as const)(
  'shows No reports for %s with %i reports: %s',
  (state, report_count, visible) => {
    const { container } = render(
      <NoReportsBadge problem={{ state, report_count }} />,
    )
    if (visible) {
      expect(screen.getByText('No reports')).toHaveAttribute(
        'data-tone',
        'warning',
      )
    } else {
      expect(container).toBeEmptyDOMElement()
    }
  },
)
