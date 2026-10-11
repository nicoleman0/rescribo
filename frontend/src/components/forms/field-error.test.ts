import { expect, test } from 'vitest'
import type { ApiError } from '@/api/request'
import { fieldError, unrenderedFieldErrors } from './field-error'

function apiError(
  fieldErrors: Record<string, string[]>,
  reason = 'invalid_request',
  detail = 'Check the submitted fields.',
) {
  return Object.assign(new Error(detail), {
    status: 400,
    reason,
    fieldErrors,
  }) as ApiError
}

test('reports a field the form never asked about', () => {
  const error = apiError({ repository: ['This field may not be blank.'] })
  expect(unrenderedFieldErrors(error)).toEqual([
    'Repository: This field may not be blank.',
  ])
})

test('leaves out a field the form asked about', () => {
  const error = apiError({
    channel_id: ['Too long.'],
    draft_version: ['A valid integer is required.'],
  })
  expect(fieldError(error, 'channel_id')).toBe('Too long.')
  expect(unrenderedFieldErrors(error)).toEqual([
    'Draft version: A valid integer is required.',
  ])
})

test('a field the form asked about counts even with no error', () => {
  const error = apiError({ title: ['Too long.'] })
  expect(fieldError(error, 'summary')).toBeUndefined()
  expect(unrenderedFieldErrors(error)).toEqual(['Title: Too long.'])
})

test('each failed request starts with no fields recorded', () => {
  fieldError(apiError({ title: ['Too long.'] }), 'title')
  expect(unrenderedFieldErrors(apiError({ title: ['Too long.'] }))).toEqual([
    'Title: Too long.',
  ])
})

test('shows an error that belongs to no field without a name', () => {
  const error = apiError({ non_field_errors: ['Expected an object.'] })
  expect(unrenderedFieldErrors(error)).toEqual(['Expected an object.'])
})

test('joins every message for a field', () => {
  const error = apiError({ channel_id: ['Too long.', 'Wrong pattern.'] })
  expect(unrenderedFieldErrors(error)).toEqual([
    'Channel id: Too long. Wrong pattern.',
  ])
})

test('puts a known code into words', () => {
  const error = apiError(
    { owner_id: ['invalid_reference'] },
    'invalid_reference',
    'Choose an existing, active record in this workspace.',
  )
  expect(unrenderedFieldErrors(error)).toEqual([
    'Owner id: Choose an active record in this workspace.',
  ])
})

test('adds no line for a bare reason code', () => {
  const error = apiError(
    { checked_slack: ['confirmation_required'] },
    'confirmation_required',
    'Confirm that you checked Slack before sending again.',
  )
  expect(unrenderedFieldErrors(error)).toEqual([])
})

test('adds no line for a message the reply already carries', () => {
  const error = apiError(
    { password: ['Password is incorrect.'] },
    'invalid_credentials',
    'Password is incorrect.',
  )
  expect(unrenderedFieldErrors(error)).toEqual([])
})

test('has nothing to report without field errors', () => {
  expect(unrenderedFieldErrors(new Error('Offline') as ApiError)).toEqual([])
})
