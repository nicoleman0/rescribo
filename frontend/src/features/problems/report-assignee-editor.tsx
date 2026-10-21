import type { ReportDetail } from '@/api/reports'
import { ReportAssigneePicker } from '@/features/inbox/report-actions'

/** A linked report's assignee as a picker that reads as text. */
export function ReportAssigneeEditor({
  workspaceId,
  report,
}: {
  workspaceId: string
  report: ReportDetail
}) {
  return (
    <div className="min-w-0 text-sm">
      <ReportAssigneePicker
        workspaceId={workspaceId}
        report={report}
        variant="ghost"
        triggerClassName="w-full md:justify-end"
      />
    </div>
  )
}
