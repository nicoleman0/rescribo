import { render } from '@testing-library/react'
import { expect, test } from 'vitest'
import { PageTitle } from './page-title'

test('sets the branded document title', () => {
  render(<PageTitle title="Inbox" />)
  expect(document.title).toBe('Inbox · Rescribo')
})
