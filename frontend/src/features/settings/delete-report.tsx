import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import type { ReportDetail } from '@/api/reports'
import { useWorkspace } from '@/components/auth/use-workspace'
import { ConfirmAction } from './confirm-action'

export function DeleteReport({ report }: { report: ReportDetail }) {
  const { workspace, role } = useWorkspace()
  const cache = useQueryClient()
  const navigate = useNavigate()
  if (role !== 'owner') return null
  return (
    <ConfirmAction
      workspaceId={workspace.id}
      path={`reports/${report.id}/delete/`}
      body={{ version: report.version }}
      label="Delete report"
      phrase="DELETE"
      scope={`Permanently delete “${report.title}”, its captured snapshot, notification history and report activity. Only content-free deletion metadata remains. The linked problem, Slack message and GitHub issue remain. Backups expire under the operator's retention policy.`}
      onSuccess={() => {
        cache.removeQueries({
          predicate: (query) => query.queryKey.includes(workspace.id),
        })
        navigate('/inbox')
      }}
    />
  )
}
