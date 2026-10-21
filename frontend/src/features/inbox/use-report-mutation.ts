import { useMutation, useQueryClient } from '@tanstack/react-query'
import { applyReport, patchReport } from '@/api/cache'
import { problemKeys } from '@/api/problems'
import { conflictingReport, reportKeys, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'

/** Show the result before the save returns. Rolled back if the save fails. */
export type OptimisticReport<TInput> = {
  reportId: string
  patch: (report: ReportDetail, input: TInput) => ReportDetail
}

/** Run a report action. A 409 shows the server's current report, and the
 * caller's form keeps its input until the member retries. */
export function useReportMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<ReportDetail>,
  onSuccess?: (report: ReportDetail) => void,
  optimistic?: OptimisticReport<TInput>,
) {
  const client = useQueryClient()
  return useMutation<ReportDetail, ApiError, TInput, { undo?: () => void }>({
    mutationFn: run,
    onMutate: async (input) => {
      if (!optimistic) return {}
      // A refetch landing after the patch would overwrite it.
      await Promise.all([
        client.cancelQueries({ queryKey: reportKeys.all(workspaceId) }),
        client.cancelQueries({ queryKey: problemKeys.all(workspaceId) }),
      ])
      const undo = patchReport(client, workspaceId, optimistic.reportId, (r) =>
        optimistic.patch(r, input),
      )
      return { undo }
    },
    onSuccess: (report) => {
      applyReport(client, workspaceId, report)
      onSuccess?.(report)
    },
    onError: (error, _input, context) => {
      context?.undo?.()
      const current = conflictingReport(error)
      if (current) applyReport(client, workspaceId, current)
    },
  })
}
