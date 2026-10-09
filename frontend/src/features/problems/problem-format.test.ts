import { expect, test } from 'vitest'
import { issueStateLabel } from './problem-format'

test('capitalizes GitHub state reasons', () => {
  expect(
    issueStateLabel({ state: 'closed', state_reason: 'not_planned' }),
  ).toBe('Closed · Not planned')
})
