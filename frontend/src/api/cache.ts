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

export function applyReport(
  client: QueryClient,
  workspaceId: string,
  report: ReportDetail,
) {
  client.setQueryData(reportKeys.detail(workspaceId, report.id), report)
  // Problem detail edits reports from its linked-report pages. Update those
  // copies now so the next edit sends the current version before refetch.
  client.setQueriesData<ProblemReportPage>(
    {
      queryKey: problemKeys.all(workspaceId),
      predicate: (query) => query.queryKey.includes('reports'),
    },
    (page) =>
      page && {
        ...page,
        results: page.results.map((row) =>
          row.id === report.id ? report : row,
        ),
      },
  )
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
