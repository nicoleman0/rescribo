import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import type { ReportPage } from '@/api/reports'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { withPage } from './inbox-query'
import { formatDate, memberName, sourceLabel } from './report-format'
import { TriageBadge } from './triage-badge'

export function ReportList({
  page,
  pageNumber,
  selectedId,
}: {
  page: ReportPage
  pageNumber: number
  selectedId?: string
}) {
  const [params] = useSearchParams()
  const search = params.toString() ? `?${params.toString()}` : ''
  return (
    <div className="grid gap-3">
      <ul
        aria-label="Reports"
        className="divide-y divide-border overflow-hidden rounded-card border border-border bg-card"
      >
        {page.results.map((report) => (
          <li key={report.id}>
            <Link
              to={`/inbox/${report.id}${search}`}
              aria-current={report.id === selectedId ? 'page' : undefined}
              className={cn(
                'grid gap-1.5 px-4 py-3 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset',
                report.id === selectedId && 'bg-selected',
              )}
            >
              <span className="flex items-start justify-between gap-3">
                <span className="min-w-0 font-medium break-words">
                  {report.title}
                </span>
                <TriageBadge state={report.triage_state} />
              </span>
              <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span>{report.customer_label || 'No customer'}</span>
                <span>{sourceLabel(report.source_kind)}</span>
                <span>
                  {report.assignee ? memberName(report.assignee) : 'Unassigned'}
                </span>
                {report.problem ? (
                  <span>Problem: {report.problem.title}</span>
                ) : null}
                <time className="font-mono" dateTime={report.created_at}>
                  {formatDate(report.created_at)}
                </time>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      <Pagination page={page} pageNumber={pageNumber} />
    </div>
  )
}

function Pagination({
  page,
  pageNumber,
}: {
  page: ReportPage
  pageNumber: number
}) {
  const [params, setParams] = useSearchParams()
  const hasPages = Boolean(page.previous || page.next)
  return (
    <nav
      aria-label="Report pages"
      className="flex items-center justify-between gap-3"
    >
      <p className="font-mono text-xs text-muted-foreground" aria-live="polite">
        {page.count} {page.count === 1 ? 'report' : 'reports'}
        {hasPages ? ` · page ${pageNumber}` : ''}
      </p>
      {hasPages ? (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!page.previous}
            onClick={() => setParams(withPage(params, pageNumber - 1))}
          >
            <ChevronLeft aria-hidden="true" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!page.next}
            onClick={() => setParams(withPage(params, pageNumber + 1))}
          >
            Next
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </nav>
  )
}
