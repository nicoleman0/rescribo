import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Button } from './button'

test.each(['default', 'outline', 'secondary', 'ghost'] as const)(
  'the %s button uses shared press feedback',
  (variant) => {
    render(<Button variant={variant}>Action</Button>)
    const button = screen.getByRole('button', { name: 'Action' })
    expect(button).toHaveClass('press')
    expect(button.className).not.toContain('translate-y-px')
    expect(button).not.toHaveClass('transition-all')
    expect(button.classList.contains('shadow-hairline')).toBe(
      variant === 'outline' || variant === 'secondary',
    )
  },
)

test.each([
  'xs',
  'sm',
  'default',
  'lg',
  'icon',
  'icon-xs',
  'icon-sm',
  'icon-lg',
] as const)('the %s button has the phone touch target minimum', (size) => {
  render(<Button size={size}>Action</Button>)
  expect(screen.getByRole('button', { name: 'Action' })).toHaveClass(
    'max-md:min-h-[44px]',
  )
})
