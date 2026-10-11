import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ApiError } from '@/api/request'
import { fieldError } from './field-error'
import { Field } from './field'
import { FormErrorMessage } from './form-error-message'

function failure() {
  return Object.assign(new Error('Check the submitted fields.'), {
    status: 400,
    reason: 'invalid_request',
    fieldErrors: {
      email: ['Enter a valid email address.'],
      role: ['"admin" is not a valid choice.'],
    },
  }) as ApiError
}

// The summary sits above the field on purpose: order in the form must not matter.
function Form({ error }: { error: ApiError }) {
  return (
    <form>
      <p role="status">
        <FormErrorMessage error={error} />
      </p>
      <Field id="email" label="Email" error={fieldError(error, 'email')} />
    </form>
  )
}

test('shows the message, then the fields the form does not render', () => {
  render(<Form error={failure()} />)
  const summary = screen.getByRole('status')
  expect(summary).toHaveTextContent(
    'Check the submitted fields. Role: "admin" is not a valid choice.',
  )
  expect(summary).not.toHaveTextContent('Enter a valid email address.')
  expect(screen.getByRole('alert')).toHaveTextContent(
    'Enter a valid email address.',
  )
})

test('keeps the wording a summary passes in', () => {
  render(
    <p role="status">
      <FormErrorMessage
        error={failure()}
        message="Check the highlighted fields."
      />
    </p>,
  )
  expect(screen.getByRole('status')).toHaveTextContent(
    'Check the highlighted fields. Email: Enter a valid email address. Role: "admin" is not a valid choice.',
  )
})

function LateField({ error }: { error: ApiError }) {
  return <Field id="email" label="Email" error={fieldError(error, 'email')} />
}

function FormWithLateField({ error }: { error: ApiError }) {
  return (
    <form>
      <p role="status">
        <FormErrorMessage error={error} />
      </p>
      <LateField error={error} />
    </form>
  )
}

test('a child field rendered after the summary may repeat its message', () => {
  render(<FormWithLateField error={failure()} />)
  expect(screen.getByRole('status')).toHaveTextContent(
    'Email: Enter a valid email address.',
  )
})
