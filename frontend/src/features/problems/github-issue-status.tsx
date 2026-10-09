import type { EngineeringIssue } from '@/api/github-issues'
import { formatDate } from '@/features/inbox/report-format'
import { issueStateLabel } from './problem-format'

const accessLabels: Record<EngineeringIssue['access'], string> = {
  ok: 'Access verified',
  inaccessible: 'Access unavailable',
  disconnected: 'Connection disconnected',
  access_lost: 'Access unavailable',
  suspended: 'App suspended',
  deleted: 'Issue deleted',
}

export function GitHubIssueStatus({ issue }: { issue: EngineeringIssue }) {
  const lastSync = issue.last_synced_at
    ? formatDate(issue.last_synced_at)
    : 'Not synced yet'
  return (
    <div className="grid gap-2 rounded-card border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            href={issue.url}
            target="_blank"
            rel="noreferrer"
          >
            #{issue.number} {issue.title}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
          <p className="text-xs text-muted-foreground">{issue.repository}</p>
        </div>
        <span className="rounded-full bg-muted px-2.5 py-1 text-xs">
          {issueStateLabel(issue)}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {accessLabels[issue.access]}
        {issue.stale ? ' · Status may be out of date' : ''}
        {' · '}Last checked {lastSync}
        {issue.refresh_status === 'pending' ? ' · Refresh queued' : ''}
        {issue.refresh_status === 'running' ? ' · Refreshing' : ''}
      </p>
      {issue.access_detail ? (
        <p role="status" className="text-sm text-muted-foreground">
          {issue.access_detail}
        </p>
      ) : null}
    </div>
  )
}
