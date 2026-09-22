import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Field } from './field'

test('connects label and inline error to the input', () => {
  render(<Field id="email" label="Email" error="Enter a valid email." />)
  expect(screen.getByRole('textbox', { name: 'Email' })).toHaveAttribute(
    'aria-invalid',
    'true',
  )
  expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email.')
})
