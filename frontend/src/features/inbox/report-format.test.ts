import { expect, test } from 'vitest'
import { actorName, formatTime } from './report-format'

test.each([
  ['slack_delivery', 'Slack delivery'],
  ['github_webhook', 'GitHub'],
  ['github_reconciliation', 'GitHub sync'],
  ['unknown_worker', 'System'],
])('labels system actor %s as %s', (actor_system, expected) => {
  expect(actorName({ actor: null, actor_system })).toBe(expected)
})

test('prefers the member name for a human actor', () => {
  expect(
    actorName({
      actor: { id: 'mem-1', display_name: 'Ada Lovelace' },
      actor_system: '',
    }),
  ).toBe('Ada Lovelace')
})

test('formats time without seconds', () => {
  expect(formatTime('2026-10-07T15:04:39Z')).not.toMatch(/:\d{2}:\d{2}/)
})
