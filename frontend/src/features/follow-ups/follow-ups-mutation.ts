import { useMutation, useQueryClient } from '@tanstack/react-query'
import { patchQuery } from '@/api/cache'
import {
  conflictingFollowUp,
  followUpKeys,
  type FollowUpDetail,
} from '@/api/follow-ups'
import type { ApiError } from '@/api/request'

/** Show the result before the save returns. Rolled back if the save fails. */
export type OptimisticFollowUp<TInput> = {
  followUpId: string
  patch: (followUp: FollowUpDetail, input: TInput) => FollowUpDetail
}

/** Run a follow-up mutation. A 409 carries the server's current row, which
 * the caller's section reconciles by refetching the detail. */
export function useFollowUpMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<FollowUpDetail>,
  onSuccess?: (followUp: FollowUpDetail) => void,
  optimistic?: OptimisticFollowUp<TInput>,
) {
  const client = useQueryClient()
  return useMutation<FollowUpDetail, ApiError, TInput, { undo?: () => void }>({
    mutationFn: run,
    onMutate: async (input) => {
      if (!optimistic) return {}
      const key = followUpKeys.detail(workspaceId, optimistic.followUpId)
      await client.cancelQueries({ queryKey: key })
      return {
        undo: patchQuery<FollowUpDetail>(client, key, (followUp) =>
          optimistic.patch(followUp, input),
        ),
      }
    },
    onSuccess: (followUp) => {
      client.setQueryData(
        followUpKeys.detail(workspaceId, followUp.id),
        followUp,
      )
      // The bucket list shows delivery_state and contact_state only, so let
      // the next refetch re-derive them.
      void client.invalidateQueries({
        queryKey: followUpKeys.all(workspaceId),
      })
      onSuccess?.(followUp)
    },
    onError: (error, _input, context) => {
      context?.undo?.()
      const current = conflictingFollowUp(error)
      if (current) {
        client.setQueryData(
          followUpKeys.detail(workspaceId, current.id),
          current,
        )
        void client.invalidateQueries({
          queryKey: followUpKeys.all(workspaceId),
        })
      }
    },
  })
}
