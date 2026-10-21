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

/** Rewrite every cached copy of a report: its detail and the linked-report
 * pages on problem detail. One home for where report copies live. */
export function patchReport(
  client: QueryClient,
  workspaceId: string,
  reportId: string,
  patch: (report: ReportDetail) => ReportDetail,
) {
  client.setQueryData<ReportDetail>(
    reportKeys.detail(workspaceId, reportId),
    (report) => report && patch(report),
  )
  client.setQueriesData<ProblemReportPage>(
    {
      queryKey: problemKeys.all(workspaceId),
      predicate: (query) => query.queryKey.includes('reports'),
    },
    (page) =>
      page && {
        ...page,
        results: page.results.map((row) =>
          row.id === reportId ? patch(row) : row,
        ),
      },
  )
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
