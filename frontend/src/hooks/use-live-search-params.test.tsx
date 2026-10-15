import { act, render, screen } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test } from 'vitest'
import { LocationProbe } from '@/test/location-probe'
import { useLiveSearchParams } from './use-live-search-params'

let update: ReturnType<typeof useLiveSearchParams>[1]

function Writer() {
  update = useLiveSearchParams()[1]
  return <LocationProbe />
}

const set = (key: string, value: string) => (current: URLSearchParams) => {
  const next = new URLSearchParams(current)
  next.set(key, value)
  return next
}

function twoQuickUpdates() {
  act(() => {
    update(set('assignee', 'unassigned'))
    update(set('triage_state', 'new'))
  })
  expect(screen.getByTestId('location').textContent).toBe(
    '/inbox?q=csv&assignee=unassigned&triage_state=new',
  )
}

afterEach(() => window.history.replaceState(null, '', '/'))

test('keeps two updates made before a re-render in a memory router', () => {
  render(
    <MemoryRouter initialEntries={['/inbox?q=csv']}>
      <Writer />
    </MemoryRouter>,
  )
  twoQuickUpdates()
})

test('keeps two updates made before a re-render in a browser router', () => {
  window.history.replaceState(null, '', '/inbox?q=csv')
  render(
    <BrowserRouter>
      <Writer />
    </BrowserRouter>,
  )
  twoQuickUpdates()
})
