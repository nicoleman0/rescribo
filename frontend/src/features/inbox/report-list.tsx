import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import type { MemberSummary, ReportPage } from '@/api/reports'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { withPage } from './inbox-query'
import {
  formatDate,
  formatShortDate,
  memberInitials,
  memberName,
} from './report-format'
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
      {/* Rows follow the list's width, which shrinks when a report is open. */}
      <div className="@container overflow-hidden rounded-card bg-card shadow-elevation-1">
        <ul
          aria-label="Reports"
          className="stagger-rows divide-y divide-border"
        >
          {page.results.map((report) => {
            const customer = report.customer_label || 'No customer'
            const date = (
              <time
                dateTime={report.created_at}
                title={formatDate(report.created_at)}
              >
                {formatShortDate(report.created_at)}
              </time>
            )
            return (
              <li key={report.id}>
                <Link
                  to={`/inbox/${report.id}${search}`}
                  aria-current={report.id === selectedId ? 'page' : undefined}
                  className={cn(
                    'relative grid min-h-11 grid-cols-[5.5rem_minmax(0,1fr)_auto] items-center gap-x-3 px-4 py-2 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset @2xl:grid-cols-[5.5rem_minmax(0,1fr)_10rem_auto_7rem] @2xl:py-0',
                    report.id === selectedId &&
                      'bg-selected before:absolute before:inset-y-2 before:left-0 before:w-0.5 before:rounded-pill before:bg-primary',
                  )}
                >
                  <span className="self-start pt-px @2xl:self-center @2xl:pt-0">
                    <TriageBadge state={report.triage_state} />
                  </span>
                  <span className="grid min-w-0 gap-0.5">
                    <span className="break-words @2xl:truncate">
                      <span className="font-medium">{report.title}</span>
                      {report.problem ? (
                        <span className="ml-2 hidden text-muted-foreground @2xl:inline">
                          <span className="sr-only">Problem: </span>
                          {report.problem.title}
                        </span>
                      ) : null}
                    </span>
                    <span className="truncate text-xs text-muted-foreground @2xl:hidden">
                      {customer} · {date}
                    </span>
                  </span>
                  <span className="hidden truncate text-muted-foreground @2xl:block">
                    {customer}
                  </span>
                  <AssigneeAvatar member={report.assignee} />
                  <span className="hidden text-right font-mono text-xs text-muted-foreground @2xl:block">
                    {date}
                  </span>
                </Link>
              </li>
            )
          })}
        </ul>
      </div>
      <Pagination page={page} pageNumber={pageNumber} />
    </div>
  )
}

function AssigneeAvatar({ member }: { member: MemberSummary | null }) {
  const name = member ? memberName(member) : 'Unassigned'
  return (
    <span className="flex justify-end" title={name}>
      {member ? (
        <Avatar size="sm" aria-hidden="true">
          <AvatarFallback className="font-medium">
            {memberInitials(member)}
          </AvatarFallback>
        </Avatar>
      ) : (
        <span
          aria-hidden="true"
          className="size-6 rounded-pill border border-dashed border-input"
        />
      )}
      <span className="sr-only">
        {member ? `Assigned to ${name}` : 'Unassigned'}
      </span>
    </span>
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
