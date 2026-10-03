import { useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  listProblemActivity,
  problemKeys,
  type ProblemActivity,
} from '@/api/problems'
import { ErrorState, LoadingState } from '@/components/states/async-states'
import { formatDate, memberName } from '@/features/inbox/report-format'
import { cn } from '@/lib/utils'
import { PageNav } from './page-nav'
import { countLabel, problemStateLabels } from './problem-format'

export function ProblemActivityList({
  workspaceId,
  problemId,
}: {
  workspaceId: string
  problemId: string
}) {
  const [page, setPage] = useState(1)
  const activity = useQuery({
    queryKey: problemKeys.activity(workspaceId, problemId, page),
    queryFn: () => listProblemActivity(workspaceId, problemId, page),
    placeholderData: keepPreviousData,
  })
  return (
    <section aria-labelledby="problem-activity" className="grid gap-3">
      <h2 id="problem-activity" className="text-base font-semibold">
        Activity
      </h2>
      {activity.isPending ? <LoadingState label="Loading activity" /> : null}
      {activity.isError ? (
        <ErrorState
          title="Could not load activity"
          onRetry={() => (page > 1 ? setPage(1) : void activity.refetch())}
          isRetrying={activity.isFetching}
        />
      ) : null}
      {activity.isError && activity.data ? (
        <ErrorState
          title="Could not refresh activity"
          description="The last loaded activity remains visible. Retry to check for newer events."
          onRetry={() => void activity.refetch()}
          isRetrying={activity.isFetching}
        />
      ) : null}
      {activity.data ? (
        <div
          aria-busy={activity.isPlaceholderData}
          className={cn(
            'grid gap-3',
            activity.isPlaceholderData && 'opacity-60',
          )}
        >
          <ol
            aria-label="Problem activity"
            className="grid gap-3 border-l border-border pl-4"
          >
            {activity.data.results.map((entry) => (
              <li key={entry.id} className="grid gap-0.5 text-sm">
                <span className="break-words">
                  <span className="font-medium">{actorName(entry)}</span>{' '}
                  {describe(entry)}
                </span>
                <time
                  dateTime={entry.created_at}
                  className="font-mono text-xs text-muted-foreground"
                >
                  {formatDate(entry.created_at)}
                </time>
              </li>
            ))}
          </ol>
          <PageNav
            label="Activity pages"
            count={countLabel(activity.data.count, 'event')}
            page={activity.data}
            pageNumber={page}
            onPage={(next) => setPage(next ?? 1)}
          />
        </div>
      ) : null}
    </section>
  )
}

const actorName = (entry: ProblemActivity) =>
  entry.actor ? memberName(entry.actor) : entry.actor_system || 'System'

function reportLink(entry: ProblemActivity): ReactNode {
  if (!entry.report) return 'a report'
  return (
    <Link
      to={`/inbox/${entry.report.id}`}
      className="text-primary underline-offset-4 hover:underline"
    >
      {entry.report.title}
    </Link>
  )
}

function problemLink(problem: { id: string; title: string }) {
  return (
    <Link
      to={`/problems/${problem.id}`}
      className="text-primary underline-offset-4 hover:underline"
    >
      {problem.title}
    </Link>
  )
}

const fieldNames: Record<string, string> = {
  title: 'title',
  summary: 'summary',
  owner: 'owner',
}

function describe(entry: ProblemActivity): ReactNode {
  switch (entry.action) {
    case 'problem.created':
      return 'created the problem'
    case 'problem.updated':
      return `changed the ${entry.changed_fields.map((name) => fieldNames[name] ?? name).join(' and ')}`
    case 'problem.state_changed':
      return entry.state
        ? `changed the status to ${problemStateLabels[entry.state]}`
        : 'changed the status'
    case 'problem.fix_confirmed':
      return 'confirmed a fix'
    case 'report.linked':
      return entry.from_problem ? (
        <>
          moved {reportLink(entry)} here from {problemLink(entry.from_problem)}
        </>
      ) : (
        <>linked {reportLink(entry)}</>
      )
    case 'report.unlinked':
      return entry.to_problem ? (
        <>
          moved {reportLink(entry)} to {problemLink(entry.to_problem)}
        </>
      ) : (
        <>ungrouped {reportLink(entry)}</>
      )
    case 'report.assigned':
      return entry.to_assignee ? (
        <>
          assigned {reportLink(entry)} to {memberName(entry.to_assignee)}
        </>
      ) : (
        <>cleared the assignee of {reportLink(entry)}</>
      )
    default:
      return 'updated the problem'
  }
}
