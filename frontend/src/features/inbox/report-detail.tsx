import { DeleteReport } from '@/features/settings/delete-report'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { getReport, reportKeys, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
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
      ![403, 404].includes((error as ApiError).status ?? 0) && failures < 2,
  })
  return (
    <section
      aria-label="Report detail"
      className="relative grid content-start gap-4 rounded-card surface-raised p-4 shadow-elevation-2 lg:max-h-[calc(100svh-3rem)] lg:overflow-y-auto"
    >
      {/* A back link on phones, a close icon beside the list on desktop. */}
      <Button
        asChild
        variant="ghost"
        size="sm"
        className={cn('w-fit lg:absolute lg:top-3 lg:right-3 lg:size-8 lg:p-0')}
      >
        <Link to={backTo}>
          <ArrowLeft aria-hidden="true" className="lg:hidden" />
          <span className="lg:sr-only">Back to reports</span>
          <X aria-hidden="true" className="size-4 max-lg:hidden" />
        </Link>
      </Button>
      {report.isPending ? <LoadingState label="Loading report" /> : null}
      {report.isError && (report.error as ApiError).status === 404 ? (
        <EmptyState
          title="Report not found"
          description="It may have been deleted, or it belongs to another workspace."
        />
      ) : null}
      {report.isError && (report.error as ApiError).status === 403 ? (
        <EmptyState
          title="Report access removed"
          description="You no longer have access to this report."
        />
      ) : null}
      {report.isError &&
      ![403, 404].includes((report.error as ApiError).status ?? 0) &&
      !report.data ? (
        <ErrorState
          title="Could not load this report"
          onRetry={() => void report.refetch()}
          isRetrying={report.isFetching}
        />
      ) : null}
      {report.isError &&
      report.data &&
      ![403, 404].includes((report.error as ApiError).status ?? 0) ? (
        <ErrorState
          title="Could not refresh this report"
          description="Your open changes are still here. Retry to check for updates."
          onRetry={() => void report.refetch()}
          isRetrying={report.isFetching}
        />
      ) : null}
      {report.data &&
      !(
        report.isError &&
        [403, 404].includes((report.error as ApiError).status ?? 0)
      ) ? (
        <ReadyState>
          <ReportDetailBody workspaceId={workspaceId} report={report.data} />
        </ReadyState>
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
        <h2 className="text-base font-semibold break-words lg:pr-8">
          {report.title}
        </h2>
        {report.description ? (
          <p className="min-w-0 break-words text-sm whitespace-pre-wrap">
            {report.description}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">No description.</p>
        )}
      </header>
      <Separator />
      <ReportTriage workspaceId={workspaceId} report={report} />
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
      <Provenance
        workspaceId={workspaceId}
        reportId={report.id}
        provenance={report.provenance}
        submittedBy={report.submitted_by}
      />
      {/* Owners only; the wrapper collapses when there is nothing to show. */}
      <div className="border-t border-border pt-4 empty:hidden">
        <DeleteReport report={report} />
      </div>
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
