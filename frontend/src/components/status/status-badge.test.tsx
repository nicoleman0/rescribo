import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { StatusBadge } from './status-badge'
import { STATUS_TONES } from './status-tone'

test.each(STATUS_TONES)(
  'renders the %s tone with a label and hidden dot',
  (tone) => {
    render(<StatusBadge tone={tone}>Label {tone}</StatusBadge>)
    const badge = screen.getByText(`Label ${tone}`)
    expect(badge).toHaveAttribute('data-tone', tone)
    expect(badge.querySelector('[aria-hidden="true"]')).not.toBeNull()
  },
)
