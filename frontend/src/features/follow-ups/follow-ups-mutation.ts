import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  conflictingFollowUp,
  followUpKeys,
  type FollowUpDetail,
} from '@/api/follow-ups'
import type { ApiError } from '@/api/request'

/** Run a follow-up mutation. A 409 carries the server's current row, which
 * the caller's section reconciles by refetching the detail. */
export function useFollowUpMutation<TInput>(
  workspaceId: string,
  run: (input: TInput) => Promise<FollowUpDetail>,
  onSuccess?: (followUp: FollowUpDetail) => void,
) {
  const client = useQueryClient()
  return useMutation<FollowUpDetail, ApiError, TInput>({
    mutationFn: run,
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
    onError: (error) => {
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
