import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { ConnectionStatusBadge } from './connection-status'

test.each([
  ['active', 'Connected', 'success'],
  ['error', 'Needs attention', 'danger'],
  ['disconnected', 'Disconnected', 'neutral'],
  [undefined, 'Not connected', 'neutral'],
] as const)(
  'shows a %s connection as %s in the %s tone',
  (status, label, tone) => {
    render(<ConnectionStatusBadge status={status} />)
    expect(screen.getByText(label)).toHaveAttribute('data-tone', tone)
  },
)
