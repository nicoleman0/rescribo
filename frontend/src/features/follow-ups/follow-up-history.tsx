import { useId } from 'react'
import type { FollowUpDetail, FollowUpHistoryItem } from '@/api/follow-ups'
import { actorName, formatDate } from '@/features/inbox/report-format'
import { useSectionClass } from './follow-up-layout'
import { SectionHeading } from './follow-up-section-heading'

export function FollowUpHistory({ followUp }: { followUp: FollowUpDetail }) {
  const headingId = useId()
  const sectionClass = useSectionClass()
  const history = (followUp.history ?? []) as FollowUpHistoryItem[]
  if (!history.length) return null
  return (
    <section aria-labelledby={headingId} className={sectionClass}>
      <SectionHeading id={headingId}>History</SectionHeading>
      <ol className="grid gap-2 border-l border-border pl-4">
        {history.map((entry) => (
          <li key={entry.id} className="grid gap-0.5 text-sm">
            <span className="break-words">
              <span className="font-medium">{actorName(entry)}</span>{' '}
              {describeHistory(entry)}
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
    </section>
  )
}

function describeHistory(entry: FollowUpHistoryItem) {
  switch (entry.action) {
    case 'follow_up.notification_approved':
      return 'approved the message for sending'
    case 'follow_up.notification_sent':
      return 'recorded the send'
    case 'follow_up.notification_failed':
      return 'marked the send failed'
    case 'follow_up.notification_cancelled':
      return 'cancelled the send'
    case 'follow_up.outcome_recorded':
      return 'recorded the outcome'
    case 'follow_up.outcome_corrected':
      return 'corrected the outcome'
    case 'follow_up.recipient_changed':
      return 'changed the recipient'
    default:
      return 'updated the follow-up'
  }
}
