import { keepPreviousData, useQueries, useQuery } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  followUpKeys,
  listFollowUps,
  type FollowUpListItem,
  type FollowUpPage,
} from '@/api/follow-ups'
import type { ApiError } from '@/api/request'
import { useWorkspace } from '@/components/auth/use-workspace'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/states/async-states'
import { touchTarget } from '@/components/layout/touch-target'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { memberName } from '@/features/inbox/report-format'
import {
  BUCKETS,
  bucketFromParams,
  withBucket,
  type Bucket,
} from './follow-ups-query'
import { bucketLabels, bucketOrder, emptyBucketCopy } from './follow-ups-format'
import { FollowUpDetailPanel } from './follow-up-detail'
import { FollowUpStatuses } from './follow-up-statuses'

const FOLLOW_UPS_REFRESH_MS = 30_000

export function FollowUpsPage() {
  const { workspace } = useWorkspace()
  const { followUpId } = useParams()
  const [params, setParams] = useSearchParams()
  const bucket = bucketFromParams(params)
  const pageValue = Number(params.get('page') ?? '1')
  const page = Number.isSafeInteger(pageValue) && pageValue > 0 ? pageValue : 1
  return (
    <div className="grid gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Follow-ups</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Approved employee messages are delivered separately from customer
            contact. Track customer outcomes here.
          </p>
        </div>
      </header>
      <BucketTabs
        workspaceId={workspace.id}
        active={bucket}
        onChange={(next) => setParams(withBucket(params, next))}
      />
      <div
        className={cn(
          'grid gap-6',
          followUpId && 'lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]',
        )}
      >
        <div
          className={cn(
            'grid content-start gap-3',
            followUpId && 'max-lg:hidden',
          )}
        >
          <FollowUpsList
            key={bucket ?? 'all'}
            workspaceId={workspace.id}
            bucket={bucket}
            page={page}
            selectedId={followUpId}
          />
        </div>
        {followUpId ? (
          <FollowUpDetailPanel
            key={followUpId}
            workspaceId={workspace.id}
            followUpId={followUpId}
          />
        ) : null}
      </div>
    </div>
  )
}

function BucketTabs({
  workspaceId,
  active,
  onChange,
}: {
  workspaceId: string
  active: Bucket | null
  onChange: (bucket: Bucket | null) => void
}) {
  const counts = useQueries({
    queries: BUCKETS.map((bucket) => ({
      queryKey: followUpKeys.list(workspaceId, bucket, 1),
      queryFn: () => listFollowUps(workspaceId, bucket, 1),
      placeholderData: keepPreviousData,
      refetchInterval: FOLLOW_UPS_REFRESH_MS,
      retry: false,
    })),
  })
  const all = useQuery({
    queryKey: followUpKeys.list(workspaceId, null, 1),
    queryFn: () => listFollowUps(workspaceId, null, 1),
    refetchInterval: FOLLOW_UPS_REFRESH_MS,
  })
  return (
    <nav aria-label="Follow-up buckets" className="grid gap-3">
      {/* One row that scrolls sideways, so the list starts near the top on a phone. */}
      <ul className="flex w-fit max-w-full gap-1 overflow-x-auto rounded-control bg-muted p-1">
        <TabButton
          label="All"
          count={all.data?.count}
          unavailable={all.isError}
          loading={all.isPending}
          active={active === null}
          onClick={() => onChange(null)}
        />
        {bucketOrder.map((bucket, index) => (
          <TabButton
            key={bucket}
            label={bucketLabels[bucket]}
            count={counts[index]?.data?.count}
            unavailable={counts[index]?.isError}
            loading={counts[index]?.isPending}
            active={active === bucket}
            onClick={() => onChange(bucket)}
          />
        ))}
      </ul>
      {all.isError || counts.some((query) => query.isError) ? (
        <ErrorState
          title="Some bucket counts could not be loaded"
          description="The bucket lists remain available. Retry to refresh the counts."
          onRetry={() => {
            void all.refetch()
            for (const query of counts) if (query.isError) void query.refetch()
          }}
          isRetrying={
            all.isFetching || counts.some((query) => query.isFetching)
          }
        />
      ) : null}
    </nav>
  )
}

function TabButton({
  label,
  count,
  unavailable = false,
  loading = false,
  active,
  onClick,
}: {
  label: string
  count: number | undefined
  unavailable?: boolean
  loading?: boolean
  active: boolean
  onClick: () => void
}) {
  return (
    <li>
      <button
        type="button"
        aria-pressed={active}
        onClick={onClick}
        className={cn(
          'inline-flex min-h-8 items-center gap-2 rounded-control px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50',
          touchTarget,
          active && 'bg-card font-medium text-foreground shadow-elevation-1',
        )}
      >
        <span>{label}</span>
        <span
          className="font-mono text-xs text-muted-foreground"
          aria-label={
            unavailable
              ? 'count unavailable'
              : loading
                ? 'count loading'
                : `${count ?? 0} items`
          }
        >
          {unavailable ? '!' : loading ? '…' : (count ?? 0)}
        </span>
      </button>
    </li>
  )
}

function FollowUpsList({
  workspaceId,
  bucket,
  page,
  selectedId,
}: {
  workspaceId: string
  bucket: Bucket | null
  page: number
  selectedId: string | undefined
}) {
  const [params, setParams] = useSearchParams()
  const query = useQuery<FollowUpPage, ApiError>({
    queryKey: followUpKeys.list(workspaceId, bucket, page),
    queryFn: () => listFollowUps(workspaceId, bucket, page),
    placeholderData: keepPreviousData,
    refetchInterval: FOLLOW_UPS_REFRESH_MS,
  })
  const search = params.toString() ? `?${params.toString()}` : ''
  if (query.isPending) return <LoadingState label="Loading follow-ups" />
  if (query.isError) {
    const error = query.error
    if (error.status === 400) {
      return (
        <EmptyState
          title="These buckets are not valid"
          description="Use one of the available buckets."
        />
      )
    }
    return (
      <ErrorState
        title="Could not load follow-ups"
        description="Check the connection and try again."
        onRetry={() => void query.refetch()}
        isRetrying={query.isFetching}
      />
    )
  }
  if (query.data.count === 0) {
    const copy = bucket ? emptyBucketCopy[bucket] : null
    return (
      <EmptyState
        title={copy?.title ?? 'No follow-ups yet'}
        description={
          copy?.description ??
          'A confirmed fix on a linked report will create one.'
        }
      />
    )
  }
  return (
    <div
      aria-busy={query.isPlaceholderData}
      className={cn('grid gap-3', query.isPlaceholderData && 'opacity-60')}
    >
      <ul
        aria-label="Follow-ups"
        className="divide-y divide-border overflow-hidden rounded-card bg-card shadow-elevation-1"
      >
        {query.data.results.map((followUp) => (
          <FollowUpRow
            key={followUp.id}
            followUp={followUp}
            selectedId={selectedId}
            search={search}
          />
        ))}
      </ul>
      <p className="font-mono text-xs text-muted-foreground">
        {query.data.count} {query.data.count === 1 ? 'follow-up' : 'follow-ups'}
      </p>
      {query.data.count > 25 ? (
        <nav aria-label="Follow-up pages" className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className={touchTarget}
            disabled={page <= 1}
            onClick={() => {
              const next = new URLSearchParams(params)
              next.set('page', String(page - 1))
              setParams(next)
            }}
          >
            Previous page
          </Button>
          <span aria-live="polite" className="text-sm text-muted-foreground">
            Page {page} of {Math.ceil(query.data.count / 25)}
          </span>
          <Button
            type="button"
            variant="outline"
            className={touchTarget}
            disabled={page >= Math.ceil(query.data.count / 25)}
            onClick={() => {
              const next = new URLSearchParams(params)
              next.set('page', String(page + 1))
              setParams(next)
            }}
          >
            Next page
          </Button>
        </nav>
      ) : null}
    </div>
  )
}

function FollowUpRow({
  followUp,
  selectedId,
  search,
}: {
  followUp: FollowUpListItem
  selectedId: string | undefined
  search: string
}) {
  return (
    <li>
      <Link
        to={`/follow-ups/${followUp.id}${search}`}
        aria-current={followUp.id === selectedId ? 'page' : undefined}
        className={cn(
          'grid gap-2 px-4 py-3 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset md:grid-cols-[minmax(0,1fr)_13rem] md:items-center md:gap-4',
          followUp.id === selectedId && 'bg-selected',
        )}
      >
        <span className="grid min-w-0 gap-1">
          <span className="font-medium break-words">
            {followUp.report_title}
          </span>
          <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{followUp.customer_label || 'No customer'}</span>
            <span>For: {memberName(followUp.recipient)}</span>
            <span className="font-mono">v{followUp.resolution_revision}</span>
          </span>
        </span>
        <FollowUpStatuses
          delivery={followUp.delivery_state}
          outcome={followUp.contact_state}
          layout="row"
        />
      </Link>
    </li>
  )
}
