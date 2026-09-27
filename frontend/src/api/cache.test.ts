import { QueryClient } from '@tanstack/react-query'
import { expect, test } from 'vitest'
import { applyProblem, applyReport } from './cache'
import { problemKeys, type ProblemDetail } from './problems'
import { reportKeys, type ReportDetail } from './reports'

function seeded() {
  const client = new QueryClient()
  const keys = [
    problemKeys.list('ws-1', {}),
    problemKeys.detail('ws-1', 'old'),
    problemKeys.reports('ws-1', 'old', 1),
    problemKeys.activity('ws-1', 'new', 1),
    reportKeys.list('ws-1', {}),
    problemKeys.detail('ws-2', 'old'),
  ]
  for (const key of keys) client.setQueryData(key, { results: [] })
  const invalidated = (key: readonly unknown[]) =>
    client.getQueryState(key)?.isInvalidated
  return { client, keys, invalidated }
}

test('a report change refreshes old and new problem views in its workspace only', () => {
  const { client, keys, invalidated } = seeded()
  const report = { id: 'rep-1', version: 4 } as ReportDetail
  applyReport(client, 'ws-1', report)
  expect(client.getQueryData(reportKeys.detail('ws-1', 'rep-1'))).toEqual(
    report,
  )
  expect(keys.slice(0, 5).map(invalidated)).toEqual([
    true,
    true,
    true,
    true,
    true,
  ])
  expect(invalidated(keys[5])).toBe(false)
})

test('a problem change refreshes embedded report summaries', () => {
  const { client, keys, invalidated } = seeded()
  const problem = { id: 'old', version: 2 } as ProblemDetail
  applyProblem(client, 'ws-1', problem)
  expect(client.getQueryData(problemKeys.detail('ws-1', 'old'))).toEqual(
    problem,
  )
  expect(invalidated(reportKeys.list('ws-1', {}))).toBe(true)
  expect(invalidated(keys[5])).toBe(false)
})

test('a report change updates its copy in cached problem report pages', () => {
  const client = new QueryClient()
  const stale = { id: 'rep-1', version: 2 } as ReportDetail
  const other = { id: 'rep-2', version: 7 } as ReportDetail
  const key = problemKeys.reports('ws-1', 'prob-1', 1)
  client.setQueryData(key, {
    count: 2,
    next: null,
    previous: null,
    results: [stale, other],
  })
  const fresh = { id: 'rep-1', version: 3 } as ReportDetail
  applyReport(client, 'ws-1', fresh)
  expect(
    client.getQueryData<{ results: ReportDetail[] }>(key)?.results,
  ).toEqual([fresh, other])
})
