import { beforeEach, expect, test, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PALETTE_STORAGE_KEY } from '@/lib/theme'
import { ThemeSettings } from './theme-settings'

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('matchMedia', () => ({ matches: false }))
  delete document.documentElement.dataset.palette
})

test('choosing Forest checks it, applies it, and stores it', async () => {
  render(<ThemeSettings />)
  const group = screen.getByRole('group', { name: 'Palette' })
  expect(group).toBeTruthy()
  expect(
    (screen.getByRole('radio', { name: 'Indigo' }) as HTMLInputElement).checked,
  ).toBe(true)

  await userEvent.click(screen.getByRole('radio', { name: 'Forest' }))

  expect(
    (screen.getByRole('radio', { name: 'Forest' }) as HTMLInputElement).checked,
  ).toBe(true)
  expect(document.documentElement.dataset.palette).toBe('forest')
  expect(localStorage.getItem(PALETTE_STORAGE_KEY)).toBe('forest')
})

test('each palette option is named by its palette', () => {
  render(<ThemeSettings />)
  const names = screen
    .getAllByRole('radio')
    .filter((radio) => radio.getAttribute('name') === 'palette')
    .map((radio) => radio.parentElement?.textContent)
  expect(names).toEqual(['Indigo', 'Forest', 'Autumn', 'Sky'])
  for (const name of names) {
    expect(screen.getByRole('radio', { name: name! })).toBeTruthy()
  }
})
