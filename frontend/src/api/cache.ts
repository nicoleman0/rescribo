import type { QueryClient } from '@tanstack/react-query'
import { problemKeys, type ProblemDetail } from './problems'
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
