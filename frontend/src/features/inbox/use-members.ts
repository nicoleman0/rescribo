import { useQuery } from '@tanstack/react-query'
import { listMembers, reportKeys } from '@/api/reports'

export function useMembers(workspaceId: string) {
  return useQuery({
    queryKey: reportKeys.members(workspaceId),
    queryFn: () => listMembers(workspaceId),
    staleTime: 60_000,
  })
}
