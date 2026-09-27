import { DeleteReport } from '@/features/settings/delete-report'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getReport, reportKeys, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Provenance } from './provenance'
import { ReportTriage } from './report-actions'
import { formatDate, memberName } from './report-format'
import { TriageBadge } from './triage-badge'

export function ReportDetailPanel({
  workspaceId,
  reportId,
}: {
  workspaceId: string
  reportId: string
}) {
  const [params] = useSearchParams()
  const backTo = `/inbox${params.toString() ? `?${params.toString()}` : ''}`
  const report = useQuery({
    queryKey: reportKeys.detail(workspaceId, reportId),
    queryFn: () => getReport(workspaceId, reportId),
    retry: (failures, error) =>
      (error as ApiError).status !== 404 && failures < 2,
  })
  return (
    <section
      aria-label="Report detail"
      className="grid content-start gap-4 rounded-card border border-border bg-card p-4"
    >
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to={backTo}>
          <ArrowLeft aria-hidden="true" />
          Back to reports
        </Link>
      </Button>
      {report.isPending ? <LoadingState label="Loading report" /> : null}
      {report.isError && (report.error as ApiError).status === 404 ? (
        <EmptyState
          title="Report not found"
          description="It may have been deleted, or it belongs to another workspace."
        />
      ) : null}
      {report.isError && (report.error as ApiError).status !== 404 ? (
        <ErrorState
          title="Could not load this report"
          onRetry={() => void report.refetch()}
          isRetrying={report.isFetching}
        />
      ) : null}
      {report.isSuccess ? (
        <ReportDetailBody workspaceId={workspaceId} report={report.data} />
      ) : null}
    </section>
  )
}

function ReportDetailBody({
  workspaceId,
  report,
}: {
  workspaceId: string
  report: ReportDetail
}) {
  return (
    <article className="grid gap-4">
      <header className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <TriageBadge state={report.triage_state} />
          <span className="font-mono text-[11px] text-muted-foreground">
            v{report.version}
          </span>
        </div>
        <h2 className="text-base font-semibold break-words">{report.title}</h2>
        {report.description ? (
          <p className="text-sm whitespace-pre-wrap">{report.description}</p>
        ) : (
          <p className="text-sm text-muted-foreground">No description.</p>
        )}
      </header>
      <Separator />
      <dl className="grid grid-cols-[8rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
        <Detail label="Customer">{report.customer_label || '—'}</Detail>
        <Detail label="Contact reference">
          {report.customer_contact_reference || '—'}
        </Detail>
        <Detail label="Affected version">
          {report.affected_version || '—'}
        </Detail>
        <Detail label="Assignee">
          {report.assignee ? memberName(report.assignee) : 'Unassigned'}
        </Detail>
        <Detail label="Submitted by">{memberName(report.submitted_by)}</Detail>
        <Detail label="Problem">
          {report.problem ? (
            <Link
              to={`/problems/${report.problem.id}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              {report.problem.title}
            </Link>
          ) : (
            'Not linked'
          )}
        </Detail>
        <Detail label="Created">
          <time dateTime={report.created_at}>
            {formatDate(report.created_at)}
          </time>
        </Detail>
      </dl>
      <Separator />
      <ReportTriage workspaceId={workspaceId} report={report} />
      <Separator />
      <DeleteReport report={report} />
      <Provenance
        provenance={report.provenance}
        submittedBy={report.submitted_by}
      />
    </article>
  )
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  )
}
