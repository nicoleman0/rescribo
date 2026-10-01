import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import {
  reportKeys,
  retryPermalink,
  type MemberSummary,
  type ReportProvenance,
} from '@/api/reports'
import { problemKeys } from '@/api/problems'
import { RetryButton } from '@/components/states/async-states'
import { formatDate, memberName, sourceLabel } from './report-format'

const isSafeLink = (value: string) => value.startsWith('https://')

/** Where a report came from. Captured text renders as plain text. */
export function Provenance({
  workspaceId,
  reportId,
  provenance: source,
  submittedBy,
}: {
  workspaceId: string
  reportId: string
  provenance: ReportProvenance
  submittedBy: MemberSummary
}) {
  const captured = (
    <time dateTime={source.captured_at}>{formatDate(source.captured_at)}</time>
  )
  return (
    <section aria-label="Provenance" className="grid gap-2 text-sm">
      <h3 className="font-medium">Source</h3>
      {source.kind === 'manual' ? (
        <p className="text-muted-foreground">
          Manual entry by {memberName(submittedBy)} on {captured}.
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
          ) : source.permalink_error ? (
            <PermalinkRetry workspaceId={workspaceId} reportId={reportId} />
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

function PermalinkRetry({
  workspaceId,
  reportId,
}: {
  workspaceId: string
  reportId: string
}) {
  const client = useQueryClient()
  const retry = useMutation({
    mutationFn: () => retryPermalink(workspaceId, reportId),
    // The source shows on both report and problem screens.
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: reportKeys.all(workspaceId) }),
        client.invalidateQueries({ queryKey: problemKeys.all(workspaceId) }),
      ]),
  })
  return (
    <div className="grid justify-items-start gap-2">
      <p className="text-muted-foreground">
        {retry.isError
          ? 'Could not reach Rescribo. Check your connection and try again.'
          : 'Slack did not return a link to the original message. The captured text above is complete.'}
      </p>
      <RetryButton
        onRetry={() => retry.mutate()}
        isRetrying={retry.isPending}
      />
    </div>
  )
}
