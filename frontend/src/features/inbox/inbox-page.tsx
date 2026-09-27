import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Plus, X } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { listReports, reportKeys } from '@/api/reports'
import type { ApiError } from '@/api/request'
import { useWorkspace } from '@/components/auth/use-workspace'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  hasActiveFilters,
  queryFromParams,
  withoutFilters,
  withPage,
} from './inbox-query'
import { ReportDetailPanel } from './report-detail'
import { ReportFilterBar } from './report-filter-bar'
import { ReportList } from './report-list'

const INBOX_REFRESH_MS = 30_000

export function InboxPage() {
  const { workspace } = useWorkspace()
  const { reportId } = useParams()
  const [params] = useSearchParams()
  const query = queryFromParams(params)

  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Inbox</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Customer reports captured from Slack or entered manually.
          </p>
        </div>
        <Button asChild>
          <Link to="/inbox/new">
            <Plus aria-hidden="true" />
            New report
          </Link>
        </Button>
      </header>
      <div
        className={cn(
          'grid gap-6',
          reportId && 'lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]',
        )}
      >
        <div
          className={cn(
            'grid content-start gap-4',
            reportId && 'max-lg:hidden',
          )}
        >
          <ReportFilterBar
            key={`${query.q ?? ''}\n${query.customer ?? ''}`}
            workspaceId={workspace.id}
            query={query}
          />
          <InboxResults workspaceId={workspace.id} selectedId={reportId} />
        </div>
        {reportId ? (
          <ReportDetailPanel
            key={reportId}
            workspaceId={workspace.id}
            reportId={reportId}
          />
        ) : null}
      </div>
    </div>
  )
}

function InboxResults({
  workspaceId,
  selectedId,
}: {
  workspaceId: string
  selectedId?: string
}) {
  const [params, setParams] = useSearchParams()
  const query = queryFromParams(params)
  const reports = useQuery({
    queryKey: reportKeys.list(workspaceId, query),
    queryFn: () => listReports(workspaceId, query),
    placeholderData: keepPreviousData,
    refetchInterval: INBOX_REFRESH_MS,
  })
  const clearFilters = (
    <Button variant="outline" onClick={() => setParams(withoutFilters(params))}>
      <X aria-hidden="true" />
      Clear filters
    </Button>
  )

  if (reports.isPending) return <LoadingState label="Loading reports" />
  if (reports.isError) {
    const error = reports.error as ApiError
    if (error.status === 404 && query.page) {
      return (
        <EmptyState
          title="This page has no reports"
          description="The list changed since this page was opened."
          action={
            <Button
              variant="outline"
              onClick={() => setParams(withPage(params, 1))}
            >
              Go to the first page
            </Button>
          }
        />
      )
    }
    if (error.status === 400) {
      return (
        <EmptyState
          title="These filters are not valid"
          description="Clear the filters and search again."
          action={clearFilters}
        />
      )
    }
    return (
      <ErrorState
        title="Could not load reports"
        description="Check the connection and try again. Your filters are kept."
        onRetry={() => void reports.refetch()}
        isRetrying={reports.isFetching}
      />
    )
  }
  if (reports.data.count === 0) {
    return hasActiveFilters(query) ? (
      <EmptyState
        title="No reports match these filters"
        description="Try a different search, or clear the filters."
        action={clearFilters}
      />
    ) : (
      <EmptyState
        title="No reports yet"
        description="Capture a Slack message with the Submit customer feedback shortcut, or use New report to enter one manually."
      />
    )
  }
  return (
    <div
      aria-busy={reports.isPlaceholderData}
      className={cn(reports.isPlaceholderData && 'opacity-60')}
    >
      <ReportList
        page={reports.data}
        pageNumber={query.page ?? 1}
        selectedId={selectedId}
      />
    </div>
  )
}
