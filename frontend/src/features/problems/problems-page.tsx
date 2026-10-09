import { useState, type FormEvent } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  listProblems,
  problemKeys,
  type ProblemPage,
  type ProblemQuery,
} from '@/api/problems'
import type { ApiError } from '@/api/request'
import { useWorkspace } from '@/components/auth/use-workspace'
import { Field } from '@/components/forms/field'
import { touchTarget } from '@/components/layout/touch-target'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { memberName } from '@/features/inbox/report-format'
import { cn } from '@/lib/utils'
import { PageNav } from './page-nav'
import { countLabel, issueStateLabel, reportCountLabel } from './problem-format'
import { NeedsReviewBadge, ProblemStateBadge } from './problem-state'
import { Badge } from '@/components/ui/badge'
import { PageTitle } from '@/components/layout/page-title'

const PROBLEMS_REFRESH_MS = 30_000

function queryFromParams(params: URLSearchParams): ProblemQuery {
  const page = Number.parseInt(params.get('page') ?? '', 10)
  return {
    q: params.get('q')?.trim() || undefined,
    page: Number.isInteger(page) && page > 1 ? page : undefined,
  }
}

function withQuery(params: URLSearchParams, query: ProblemQuery) {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(query)) {
    if (value) next.set(key, String(value))
    else next.delete(key)
  }
  return next
}

export function ProblemsPage() {
  const { workspace } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const query = queryFromParams(params)
  return (
    <div className="animate-page-enter grid gap-6">
      <PageTitle title="Problems" />
      <header>
        <h1 className="text-xl font-semibold">Problems</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Related reports grouped into one piece of work. Create a problem from
          a report in the Inbox.
        </p>
      </header>
      <ProblemSearch
        key={query.q ?? ''}
        initial={query.q ?? ''}
        onSearch={(q) => setParams(withQuery(params, { q, page: undefined }))}
      />
      <ProblemResults workspaceId={workspace.id} query={query} />
    </div>
  )
}

function ProblemSearch({
  initial,
  onSearch,
}: {
  initial: string
  onSearch: (q: string) => void
}) {
  const [text, setText] = useState(initial)
  function submit(event: FormEvent) {
    event.preventDefault()
    onSearch(text.trim())
  }
  return (
    <form
      role="search"
      className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
      onSubmit={submit}
    >
      <Field
        id="problem-search"
        label="Search problems"
        type="search"
        placeholder="Title or summary"
        value={text}
        maxLength={200}
        onChange={(event) => setText(event.target.value)}
      />
      <Button type="submit" size="lg" className={cn('h-10', touchTarget)}>
        <Search aria-hidden="true" />
        Search
      </Button>
    </form>
  )
}

function ProblemResults({
  workspaceId,
  query,
}: {
  workspaceId: string
  query: ProblemQuery
}) {
  const [params, setParams] = useSearchParams()
  const problems = useQuery({
    queryKey: problemKeys.list(workspaceId, query),
    queryFn: () => listProblems(workspaceId, query),
    placeholderData: keepPreviousData,
    refetchInterval: PROBLEMS_REFRESH_MS,
  })
  const clearSearch = (
    <Button
      variant="outline"
      className={touchTarget}
      onClick={() =>
        setParams(withQuery(params, { q: undefined, page: undefined }))
      }
    >
      <X aria-hidden="true" />
      Clear search
    </Button>
  )

  if (problems.isPending) return <LoadingState label="Loading problems" />
  if (problems.isError) {
    const error = problems.error as ApiError
    if (error.status === 404 && query.page) {
      return (
        <EmptyState
          title="This page has no problems"
          description="The list changed since this page was opened."
          action={
            <Button
              variant="outline"
              className={touchTarget}
              onClick={() => setParams(withQuery(params, { page: undefined }))}
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
          title="This search is not valid"
          description="Use a shorter search, or clear it."
          action={clearSearch}
        />
      )
    }
    return (
      <ErrorState
        title="Could not load problems"
        description="Check the connection and try again. Your search is kept."
        onRetry={() => void problems.refetch()}
        isRetrying={problems.isFetching}
      />
    )
  }
  if (problems.data.count === 0) {
    return query.q ? (
      <EmptyState
        title="No problems match this search"
        description="Try different words, or clear the search."
        action={clearSearch}
      />
    ) : (
      <EmptyState
        title="No problems yet"
        description="Open a report in the Inbox and choose Create problem to group it."
      />
    )
  }
  return (
    <ReadyState
      aria-busy={problems.isPlaceholderData}
      className={cn('grid gap-3', problems.isPlaceholderData && 'opacity-60')}
    >
      <ProblemList page={problems.data} />
      <PageNav
        label="Problem pages"
        count={countLabel(problems.data.count, 'problem')}
        page={problems.data}
        pageNumber={query.page ?? 1}
        onPage={(page) => setParams(withQuery(params, { page }))}
      />
    </ReadyState>
  )
}

function ProblemList({ page }: { page: ProblemPage }) {
  return (
    <ul
      aria-label="Problems"
      className="stagger-rows divide-y divide-border overflow-hidden rounded-card bg-card shadow-elevation-1"
    >
      {page.results.map((problem) => (
        <li key={problem.id}>
          <Link
            to={`/problems/${problem.id}`}
            className="grid gap-1.5 px-4 py-3 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:ring-inset"
          >
            <span className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
              <span className="min-w-0 grow basis-48 font-medium break-words">
                {problem.title}
              </span>
              <span className="flex min-w-0 flex-wrap items-center gap-1">
                {problem.needs_review ? <NeedsReviewBadge /> : null}
                <ProblemStateBadge state={problem.state} />
                {problem.engineering_issue ? (
                  <Badge variant="outline">
                    GitHub #{problem.engineering_issue.number} ·{' '}
                    {issueStateLabel(problem.engineering_issue)}
                    {problem.engineering_issue.stale ? ' · Stale' : ''}
                    {problem.engineering_issue.access !== 'ok'
                      ? ' · Access issue'
                      : ''}
                  </Badge>
                ) : null}
              </span>
            </span>
            {problem.summary_excerpt ? (
              <span className="text-sm break-words text-muted-foreground">
                {problem.summary_excerpt}
              </span>
            ) : null}
            <span className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span>
                {problem.owner
                  ? `Owner: ${memberName(problem.owner)}`
                  : 'No owner'}
              </span>
              <span className="font-mono">
                {reportCountLabel(problem.report_count)}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
