import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { TriageBadge } from './triage-badge'

test.each([
  ['new', 'New', 'info'],
  ['linked', 'Linked', 'success'],
  ['dismissed', 'Dismissed', 'neutral'],
] as const)('shows a %s report in its tone', (state, label, tone) => {
  render(<TriageBadge state={state} />)
  expect(screen.getByText(label)).toHaveAttribute('data-tone', tone)
})
