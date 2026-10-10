import { useId, useState, type SyntheticEvent } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { listProblems, problemKeys, type ProblemListItem } from '@/api/problems'
import type { ApiError } from '@/api/request'
import { touchTarget } from '@/components/layout/touch-target'
import { Field } from '@/components/forms/field'
import {
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { PageNav } from './page-nav'
import { countLabel, reportCountLabel } from './problem-format'
import { ProblemStateBadge } from './problem-state'

/** Search and choose one problem. The caller owns the confirm action. */
export function ProblemPicker({
  workspaceId,
  excludeId,
  selectedId,
  onSelect,
  disabled = false,
}: {
  workspaceId: string
  excludeId?: string
  selectedId?: string
  onSelect: (problem: ProblemListItem) => void
  disabled?: boolean
}) {
  const id = useId()
  const [text, setText] = useState('')
  const [query, setQuery] = useState({ q: '', page: 1 })
  const request = {
    q: query.q || undefined,
    page: query.page > 1 ? query.page : undefined,
  }
  const problems = useQuery({
    queryKey: problemKeys.list(workspaceId, request),
    queryFn: () => listProblems(workspaceId, request),
    placeholderData: keepPreviousData,
  })

  function search(event: SyntheticEvent) {
    event.preventDefault()
    setQuery({ q: text.trim(), page: 1 })
  }

  const choices =
    problems.data?.results.filter((problem) => problem.id !== excludeId) ?? []

  return (
    <div className="grid gap-3">
      {/* A nested form would submit the caller's form, so search on Enter here. */}
      <div
        role="search"
        aria-label="Problems to choose from"
        className="flex items-end gap-2"
      >
        <div className="min-w-0 flex-1">
          <Field
            id={`${id}-search`}
            label="Find a problem"
            type="search"
            placeholder="Title or summary"
            value={text}
            maxLength={200}
            disabled={disabled}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') search(event)
            }}
          />
        </div>
        <Button
          type="button"
          variant="outline"
          className="h-9"
          disabled={disabled}
          onClick={search}
        >
          <Search aria-hidden="true" />
          Search
        </Button>
      </div>
      {problems.isPending ? <LoadingState label="Loading problems" /> : null}
      {problems.isError && !problems.data ? (
        <ErrorState
          title="Could not load problems"
          description={
            (problems.error as ApiError).status === 404
              ? 'The list changed. Search again.'
              : 'Check the connection and try again.'
          }
          onRetry={() => {
            if ((problems.error as ApiError).status === 404) {
              setQuery({ ...query, page: 1 })
            } else {
              void problems.refetch()
            }
          }}
          isRetrying={problems.isFetching}
        />
      ) : null}
      {problems.isError && problems.data ? (
        <ErrorState
          title="Could not refresh problems"
          description="The previous results remain available. Retry to check for updates."
          onRetry={() => void problems.refetch()}
          isRetrying={problems.isFetching}
        />
      ) : null}
      {problems.data ? (
        <ReadyState className="grid gap-3">
          {problems.data && choices.length === 0 ? (
            <p role="status" className="text-sm text-muted-foreground">
              {query.q
                ? 'No problems match this search. Try other words, or create a new problem.'
                : 'There are no other problems yet. Create a new problem instead.'}
            </p>
          ) : null}
          {problems.data && choices.length > 0 ? (
            <fieldset
              disabled={disabled}
              aria-busy={problems.isPlaceholderData}
              className={cn(
                'grid gap-2',
                problems.isPlaceholderData && 'opacity-60',
              )}
            >
              <legend className="mb-2 text-sm font-medium">Problems</legend>
              <ul className="divide-y divide-border overflow-hidden rounded-card border border-border">
                {choices.map((problem) => (
                  <li key={problem.id}>
                    <label
                      className={cn(
                        'grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-start gap-3 px-3 py-2.5 hover:bg-muted has-checked:bg-selected has-focus-visible:ring-3 has-focus-visible:ring-ring/50 has-focus-visible:ring-inset',
                        touchTarget,
                      )}
                    >
                      <input
                        type="radio"
                        name={`${id}-problem`}
                        value={problem.id}
                        checked={selectedId === problem.id}
                        onChange={() => onSelect(problem)}
                        className="mt-1 accent-primary"
                      />
                      <span className="grid gap-1">
                        <span className="font-medium break-words">
                          {problem.title}
                        </span>
                        <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          <ProblemStateBadge state={problem.state} />
                          <span className="font-mono">
                            {reportCountLabel(problem.report_count)}
                          </span>
                        </span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
              <PageNav
                label="Problem search pages"
                count={countLabel(problems.data.count, 'problem')}
                page={problems.data}
                pageNumber={query.page}
                onPage={(page) => setQuery({ ...query, page: page ?? 1 })}
              />
            </fieldset>
          ) : null}
        </ReadyState>
      ) : null}
    </div>
  )
}
