import { expect, test } from 'vitest'
import type { ProblemActivity } from '@/api/problems'
import { describeUpdate, groupActivity } from './activity-format'

const ada = { id: 'mem-2', display_name: 'Ada Lovelace' }
const sam = { id: 'mem-3', display_name: 'Sam Rivera' }

const link = (minute: number, changes: Partial<ProblemActivity> = {}) =>
  ({
    id: `act-${minute}-${changes.actor?.id ?? ada.id}`,
    action: 'report.linked',
    actor: ada,
    actor_system: '',
    created_at: new Date(Date.UTC(2026, 8, 19, 12, minute)).toISOString(),
    report: { id: `rep-${minute}`, title: `Report ${minute}` },
    from_problem: null,
    to_problem: null,
    from_assignee: null,
    to_assignee: null,
    changed_fields: [],
    state: null,
    ...changes,
  }) satisfies ProblemActivity

const shape = (entries: ProblemActivity[]) =>
  groupActivity(entries).map((item) =>
    item.kind === 'links'
      ? item.entries.map((entry) => entry.id)
      : item.entry.id,
  )

test('folds consecutive links by one member into one group', () => {
  expect(shape([link(30), link(25), link(21), link(20)])).toEqual([
    ['act-30-mem-2', 'act-25-mem-2', 'act-21-mem-2', 'act-20-mem-2'],
  ])
})

test('keeps a single link as an entry', () => {
  expect(shape([link(30)])).toEqual(['act-30-mem-2'])
})

test('a move breaks a batch', () => {
  const moved = link(25, { from_problem: { id: 'prob-2', title: 'Billing' } })
  expect(shape([link(30), moved, link(20)])).toEqual([
    'act-30-mem-2',
    'act-25-mem-2',
    'act-20-mem-2',
  ])
})

test('another member breaks a batch', () => {
  expect(
    shape([link(30), link(29), link(28, { actor: sam }), link(27)]),
  ).toEqual([['act-30-mem-2', 'act-29-mem-2'], 'act-28-mem-3', 'act-27-mem-2'])
})

test('a gap over 10 minutes breaks a batch', () => {
  expect(shape([link(40), link(30), link(19)])).toEqual([
    ['act-40-mem-2', 'act-30-mem-2'],
    'act-19-mem-2',
  ])
})

test.each([
  [['needs_review'], 'flagged the problem for review'],
  [
    ['state', 'needs_review'],
    'changed the status and flagged the problem for review',
  ],
  [['title', 'summary'], 'changed the title and summary'],
  [['fix_note'], 'changed the fix note'],
  [[], 'updated the problem'],
])('describes changed fields %j', (fields, text) => {
  expect(describeUpdate(fields)).toBe(text)
})
