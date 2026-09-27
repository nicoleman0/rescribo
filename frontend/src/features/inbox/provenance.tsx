import { ExternalLink } from 'lucide-react'
import type { MemberSummary, ReportProvenance } from '@/api/reports'
import { formatDate, memberName, sourceLabel } from './report-format'

const isSafeLink = (value: string) => value.startsWith('https://')

/** Where a report came from. Captured text renders as plain text. */
export function Provenance({
  provenance: source,
  submittedBy,
}: {
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
