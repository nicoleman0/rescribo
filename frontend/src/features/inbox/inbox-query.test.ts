import { expect, test } from 'vitest'
import {
  hasActiveFilters,
  queryFromParams,
  withFilters,
  withoutFilters,
  withPage,
} from './inbox-query'

test('passes URL filters through so the API validates them', () => {
  const query = queryFromParams(
    new URLSearchParams(
      'q=+csv+&triage_state=archived&source_kind=slack&page=0',
    ),
  )
  expect(query).toEqual({
    q: 'csv',
    customer: undefined,
    triage_state: 'archived',
    assignee: undefined,
    source_kind: 'slack',
    page: undefined,
  })
  expect(hasActiveFilters(query)).toBe(true)
  expect(hasActiveFilters(queryFromParams(new URLSearchParams('page=2')))).toBe(
    false,
  )
})

test('treats blank enum filters as unset', () => {
  const query = queryFromParams(
    new URLSearchParams('triage_state=&source_kind=+'),
  )
  expect(query.triage_state).toBeUndefined()
  expect(query.source_kind).toBeUndefined()
})

test('filter changes reset the page and keep unrelated parameters', () => {
  const params = new URLSearchParams('q=csv&page=3')
  expect(withFilters(params, { customer: ' acme ', q: '' }).toString()).toBe(
    'customer=acme',
  )
  expect(withPage(params, 1).toString()).toBe('q=csv')
  expect(withoutFilters(params).toString()).toBe('')
})
