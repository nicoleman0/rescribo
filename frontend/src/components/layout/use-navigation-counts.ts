import { useQuery } from '@tanstack/react-query'
import { listFollowUps, followUpKeys } from '@/api/follow-ups'
import { listReports, reportKeys } from '@/api/reports'

export const NAV_COUNTS_REFRESH_MS = 30_000

export function useNavigationCounts(workspaceId?: string) {
  const reports = useQuery({
    queryKey: reportKeys.list(workspaceId ?? '', { triage_state: 'new' }),
    queryFn: () => listReports(workspaceId!, { triage_state: 'new' }),
    enabled: Boolean(workspaceId),
    refetchInterval: NAV_COUNTS_REFRESH_MS,
  })
  const followUps = useQuery({
    queryKey: followUpKeys.list(workspaceId ?? '', 'needs_approval', 1),
    queryFn: () => listFollowUps(workspaceId!, 'needs_approval', 1),
    enabled: Boolean(workspaceId),
    refetchInterval: NAV_COUNTS_REFRESH_MS,
  })
  return {
    reports: reports.isSuccess ? reports.data.count : undefined,
    followUps: followUps.isSuccess ? followUps.data.count : undefined,
  }
}
