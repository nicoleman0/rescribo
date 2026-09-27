import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, ExternalLink } from 'lucide-react'
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
import { formatDate, memberName, sourceLabel } from './report-format'
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
      {report.isSuccess ? <ReportDetailBody report={report.data} /> : null}
    </section>
  )
}

function ReportDetailBody({ report }: { report: ReportDetail }) {
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
          {report.problem ? report.problem.title : 'Not linked'}
        </Detail>
        <Detail label="Created">
          <time dateTime={report.created_at}>
            {formatDate(report.created_at)}
          </time>
        </Detail>
      </dl>
      <Separator />
      <Provenance report={report} />
    </article>
  )
}

const isSafeLink = (value: string) => value.startsWith('https://')

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </>
  )
}

function Provenance({ report }: { report: ReportDetail }) {
  const source = report.provenance
  const captured = (
    <time dateTime={source.captured_at}>{formatDate(source.captured_at)}</time>
  )
  return (
    <section aria-label="Provenance" className="grid gap-2 text-sm">
      <h3 className="font-medium">Source</h3>
      {source.kind === 'manual' ? (
        <p className="text-muted-foreground">
          Manual entry by {memberName(report.submitted_by)} on {captured}.
        </p>
      ) : (
        <>
          <p className="text-muted-foreground">
            {sourceLabel(source.kind)} message
            {source.author_display_name
              ? ` by ${source.author_display_name}`
              : ''}
            . Captured on {captured}; this is not a live copy.
          </p>
          {source.snapshot_text ? (
            <blockquote className="rounded-control border-l-2 border-border bg-muted px-3 py-2 whitespace-pre-wrap">
              {source.snapshot_text}
            </blockquote>
          ) : null}
          {isSafeLink(source.permalink) ? (
            <a
              href={source.permalink}
              target="_blank"
              rel="noreferrer"
              className="inline-flex w-fit items-center gap-1 text-primary underline-offset-4 hover:underline"
            >
              Open original message
              <ExternalLink aria-hidden="true" className="size-3.5" />
            </a>
          ) : (
            <p className="text-muted-foreground">
              The message link is not available yet.
            </p>
          )}
        </>
      )}
    </section>
  )
}
