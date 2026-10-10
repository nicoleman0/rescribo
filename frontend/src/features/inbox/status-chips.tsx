import { keepPreviousData, useQueries } from '@tanstack/react-query'
import { listReports, reportKeys, type InboxQuery } from '@/api/reports'
import { RetryButton } from '@/components/states/async-states'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'
import { INBOX_REFRESH_MS, triageStates } from './inbox-query'

const chips = [{ value: undefined, label: 'All' }, ...triageStates]

/** Status filter with a count per chip. Each count is the list query for
 * that chip, so the active chip shares its request with the visible list. */
export function StatusChips({
  workspaceId,
  query,
  onChange,
}: {
  workspaceId: string
  query: InboxQuery
  onChange: (triageState: string) => void
}) {
  const counts = useQueries({
    queries: chips.map((chip) => {
      const chipQuery = { ...query, triage_state: chip.value, page: undefined }
      return {
        queryKey: reportKeys.list(workspaceId, chipQuery),
        queryFn: () => listReports(workspaceId, chipQuery),
        placeholderData: keepPreviousData,
        refetchInterval: INBOX_REFRESH_MS,
      }
    }),
  })
  const activeIndex = chips.findIndex(
    (chip) => chip.value === query.triage_state,
  )
  // The list already offers a retry when its own request fails.
  const showRetry =
    counts[activeIndex]?.isSuccess && counts.some((count) => count.isError)

  return (
    <div className="flex flex-wrap items-center gap-2 max-md:w-full">
      <div
        role="group"
        aria-label="Status"
        className="flex max-w-full gap-0.5 overflow-x-auto rounded-card bg-muted p-0.5"
      >
        {chips.map((chip, index) => {
          const count = counts[index]
          const active = index === activeIndex
          return (
            <button
              key={chip.label}
              type="button"
              aria-pressed={active}
              onClick={() => onChange(chip.value ?? '')}
              className={cn(
                'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-control px-2.5 text-sm whitespace-nowrap text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50',
                touchTarget,
                active &&
                  'bg-card font-medium text-foreground shadow-elevation-1',
              )}
            >
              {chip.label}
              <ChipCount
                count={count?.data?.count}
                loading={count?.isPending ?? true}
                unavailable={count?.isError ?? false}
              />
            </button>
          )
        })}
      </div>
      {showRetry ? (
        <RetryButton
          onRetry={() => {
            for (const count of counts) if (count.isError) void count.refetch()
          }}
          isRetrying={counts.some((count) => count.isFetching)}
        />
      ) : null}
    </div>
  )
}

function ChipCount({
  count,
  loading,
  unavailable,
}: {
  count: number | undefined
  loading: boolean
  unavailable: boolean
}) {
  const [shown, spoken] = unavailable
    ? ['–', 'count unavailable']
    : loading
      ? ['…', 'count loading']
      : [String(count), String(count)]
  return (
    <span className="min-w-[2ch] text-center font-mono text-xs tabular-nums text-muted-foreground">
      <span aria-hidden="true">{shown}</span>
      <span className="sr-only">, {spoken}</span>
    </span>
  )
}
