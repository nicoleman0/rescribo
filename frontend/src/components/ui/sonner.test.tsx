import { act, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { toast } from 'sonner'
import { Toaster } from './sonner'

test('a success toast is announced politely and does not take focus', async () => {
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  }))
  render(
    <>
      <button type="button">Elsewhere</button>
      <Toaster />
    </>,
  )
  const button = screen.getByRole('button', { name: 'Elsewhere' })
  button.focus()
  act(() => void toast.success('Assigned to Ana'))
  const message = await screen.findByText('Assigned to Ana')
  expect(message.closest('[aria-live="polite"]')).not.toBeNull()
  expect(button).toHaveFocus()
})
