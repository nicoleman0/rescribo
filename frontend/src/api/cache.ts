import type { QueryClient } from '@tanstack/react-query'
import {
  problemKeys,
  type ProblemDetail,
  type ProblemReportPage,
} from './problems'
import { reportKeys, type ReportDetail } from './reports'

// A triage change moves reports between problems and changes counts,
// timelines, and embedded summaries, so refresh both workspace namespaces.
function refreshTriage(client: QueryClient, workspaceId: string) {
  void client.invalidateQueries({ queryKey: reportKeys.all(workspaceId) })
  void client.invalidateQueries({ queryKey: problemKeys.all(workspaceId) })
}

/** Rewrite one cached record. Returns a function that puts the old value
 * back, for an optimistic update that must roll back. */
export function patchQuery<T>(
  client: QueryClient,
  key: readonly unknown[],
  patch: (record: T) => T,
) {
  const previous = client.getQueryData<T>(key)
  if (previous === undefined) return () => {}
  client.setQueryData<T>(key, patch(previous))
  return () => client.setQueryData<T>(key, previous)
}

/** Rewrite every cached copy of a report: its detail and the linked-report
 * pages on problem detail. One home for where report copies live. Returns
 * a function that restores the copies it changed. */
export function patchReport(
  client: QueryClient,
  workspaceId: string,
  reportId: string,
  patch: (report: ReportDetail) => ReportDetail,
) {
  const undoDetail = patchQuery<ReportDetail>(
    client,
    reportKeys.detail(workspaceId, reportId),
    patch,
  )
  const pages = {
    queryKey: problemKeys.all(workspaceId),
    predicate: (query: { queryKey: readonly unknown[] }) =>
      query.queryKey.includes('reports'),
  }
  const before = client.getQueriesData<ProblemReportPage>(pages)
  client.setQueriesData<ProblemReportPage>(
    pages,
    (page) =>
      page && {
        ...page,
        results: page.results.map((row) =>
          row.id === reportId ? patch(row) : row,
        ),
      },
  )
  return () => {
    undoDetail()
    for (const [key, page] of before) client.setQueryData(key, page)
  }
}

export function applyReport(
  client: QueryClient,
  workspaceId: string,
  report: ReportDetail,
) {
  // The detail key is written even when empty, so a fresh reply seeds it.
  client.setQueryData(reportKeys.detail(workspaceId, report.id), report)
  // Problem detail edits reports from its linked-report pages. Update those
  // copies now so the next edit sends the current version before refetch.
  patchReport(client, workspaceId, report.id, () => report)
  refreshTriage(client, workspaceId)
}

export function applyProblem(
  client: QueryClient,
  workspaceId: string,
  problem: ProblemDetail,
) {
  client.setQueryData(problemKeys.detail(workspaceId, problem.id), problem)
  refreshTriage(client, workspaceId)
}
