import { useMutation, useQueryClient } from '@tanstack/react-query'
import { applyProblem } from '@/api/cache'
import { conflictingProblem, type ProblemDetail } from '@/api/problems'
import type { ApiError } from '@/api/request'

/** Run a problem edit. A 409 shows the server's current problem, and the
 * caller's form keeps its input until the member retries. */
export function useProblemMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<ProblemDetail>,
  onSuccess?: (problem: ProblemDetail) => void,
) {
  const client = useQueryClient()
  return useMutation<ProblemDetail, ApiError, TInput>({
    mutationFn: run,
    onSuccess: (problem) => {
      applyProblem(client, workspaceId, problem)
      onSuccess?.(problem)
    },
    onError: (error) => {
      const current = conflictingProblem(error)
      if (current) applyProblem(client, workspaceId, current)
    },
  })
}
