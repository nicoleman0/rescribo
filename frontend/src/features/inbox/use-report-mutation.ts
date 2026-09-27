import { useMutation, useQueryClient } from '@tanstack/react-query'
import { applyReport } from '@/api/cache'
import { conflictingReport, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'

/** Run a report action. A 409 shows the server's current report, and the
 * caller's form keeps its input until the member retries. */
export function useReportMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<ReportDetail>,
  onSuccess?: (report: ReportDetail) => void,
) {
  const client = useQueryClient()
  return useMutation<ReportDetail, ApiError, TInput>({
    mutationFn: run,
    onSuccess: (report) => {
      applyReport(client, workspaceId, report)
      onSuccess?.(report)
    },
    onError: (error) => {
      const current = conflictingReport(error)
      if (current) applyReport(client, workspaceId, current)
    },
  })
}
