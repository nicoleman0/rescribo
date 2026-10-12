import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { Markdown } from './markdown'

// The renderer chunk is rejected in this file only, so the other tests keep
// the real module.
vi.mock('./markdown-renderer', () => {
  throw new Error('chunk failed')
})

test('keeps the body visible and reports a renderer load failure', async () => {
  render(<Markdown>{'# Private body'}</Markdown>)
  const body = await screen.findByText(
    (_, element) => element?.textContent === '# Private body',
  )
  expect(body).toHaveClass('whitespace-pre-wrap')
  expect(
    screen.getByText('Formatted preview could not load.'),
  ).toBeInTheDocument()
})
