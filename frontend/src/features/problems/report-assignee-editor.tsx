import { useId, useState } from 'react'
import type { ReportDetail } from '@/api/reports'
import { Button } from '@/components/ui/button'
import { AssignReportForm } from '@/features/inbox/report-actions'
import { memberName } from '@/features/inbox/report-format'
import { cn } from '@/lib/utils'

/** A linked report's assignee as text. Change opens the inbox assignee form;
 * only Done closes it, so a failed save keeps the pick and the error. Renders
 * two grid items: the toggle, and the form across the whole row. */
export function ReportAssigneeEditor({
  workspaceId,
  report,
}: {
  workspaceId: string
  report: ReportDetail
}) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  return (
    <>
      <div className="flex min-w-0 items-center gap-1 text-sm md:justify-end">
        <span className="min-w-0 truncate text-muted-foreground">
          <span className="sr-only">Assignee: </span>
          {report.assignee ? memberName(report.assignee) : 'Unassigned'}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={cn('shrink-0')}
          aria-expanded={editing}
          aria-controls={editing ? id : undefined}
          aria-label={`${editing ? 'Done changing' : 'Change'} the assignee for ${report.title}`}
          onClick={() => setEditing(!editing)}
        >
          {editing ? 'Done' : 'Change'}
        </Button>
      </div>
      {editing ? (
        <div id={id} className="pt-2 md:col-span-2">
          <AssignReportForm workspaceId={workspaceId} report={report} />
        </div>
      ) : null}
    </>
  )
}
