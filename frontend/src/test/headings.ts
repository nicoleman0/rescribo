import { screen } from '@testing-library/react'
import { expect } from 'vitest'

/** A page has one level-1 heading, and it is this one. */
export function expectOneH1(name: string) {
  const h1s = screen.getAllByRole('heading', { level: 1 })
  expect(h1s.map((h) => h.textContent)).toEqual([name])
}
