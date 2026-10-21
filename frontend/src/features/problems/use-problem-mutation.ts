import { useMutation, useQueryClient } from '@tanstack/react-query'
import { applyProblem, patchQuery } from '@/api/cache'
import {
  conflictingProblem,
  problemKeys,
  type ProblemDetail,
} from '@/api/problems'
import type { ApiError } from '@/api/request'

/** Show the result before the save returns. Rolled back if the save fails. */
export type OptimisticProblem<TInput> = {
  problemId: string
  patch: (problem: ProblemDetail, input: TInput) => ProblemDetail
}

/** Run a problem edit. A 409 shows the server's current problem, and the
 * caller's form keeps its input until the member retries. */
export function useProblemMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<ProblemDetail>,
  onSuccess?: (problem: ProblemDetail) => void,
  optimistic?: OptimisticProblem<TInput>,
) {
  const client = useQueryClient()
  return useMutation<ProblemDetail, ApiError, TInput, { undo?: () => void }>({
    mutationFn: run,
    onMutate: async (input) => {
      if (!optimistic) return {}
      const key = problemKeys.detail(workspaceId, optimistic.problemId)
      await client.cancelQueries({ queryKey: key })
      return {
        undo: patchQuery<ProblemDetail>(client, key, (problem) =>
          optimistic.patch(problem, input),
        ),
      }
    },
    onSuccess: (problem) => {
      applyProblem(client, workspaceId, problem)
      onSuccess?.(problem)
    },
    onError: (error, _input, context) => {
      context?.undo?.()
      const current = conflictingProblem(error)
      if (current) applyProblem(client, workspaceId, current)
    },
  })
}
