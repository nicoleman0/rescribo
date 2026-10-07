import type {
  FollowUpContactState,
  FollowUpNotificationState,
} from '@/api/follow-ups'
import type { StatusTone } from '@/components/status/status-tone'
import { BUCKETS, type Bucket } from './follow-ups-query'

export const bucketLabels: Record<Bucket, string> = {
  needs_approval: 'Needs approval',
  delivery_problem: 'Delivery problem',
  awaiting_contact: 'Awaiting contact',
  awaiting_confirmation: 'Awaiting confirmation',
  completed: 'Completed',
}

export const emptyBucketCopy: Record<
  Bucket,
  { title: string; description: string }
> = {
  needs_approval: {
    title: 'No follow-ups waiting for approval',
    description: 'A confirmed fix on a linked report will create one.',
  },
  delivery_problem: {
    title: 'No delivery problems',
    description: 'Failed or uncertain sends will land here.',
  },
  awaiting_contact: {
    title: 'Nothing awaiting contact',
    description: 'A sent message will appear here until the customer replies.',
  },
  awaiting_confirmation: {
    title: 'Nothing awaiting confirmation',
    description:
      'Contacted customers will appear here until the outcome is set.',
  },
  completed: {
    title: 'No completed follow-ups yet',
    description:
      'Confirmed, still-affected, and no-response outcomes move here.',
  },
}

export const bucketOrder: readonly Bucket[] = BUCKETS

export const contactStateLabels: Record<FollowUpContactState, string> = {
  pending: 'Pending',
  contacted: 'Contacted',
  confirmed: 'Confirmed',
  still_affected: 'Still affected',
  no_response: 'No response',
}

export const contactStateOrder: readonly FollowUpContactState[] = [
  'pending',
  'contacted',
  'confirmed',
  'still_affected',
  'no_response',
]

void contactStateOrder

export const deliveryStateLabels: Record<FollowUpNotificationState, string> = {
  draft: 'Draft',
  queued: 'Queued',
  failed: 'Failed',
  uncertain: 'Uncertain',
  sent: 'Sent',
  cancelled: 'Cancelled',
}

// A demo send uses a fake Slack client, so its result is labelled as simulated.
export const deliveryLabel = (
  state: FollowUpNotificationState,
  simulated: boolean,
) =>
  simulated && state === 'sent'
    ? 'Sent (simulated)'
    : deliveryStateLabels[state]

export const deliveryTones: Record<FollowUpNotificationState, StatusTone> = {
  draft: 'neutral',
  queued: 'progress',
  failed: 'danger',
  uncertain: 'warning',
  sent: 'success',
  cancelled: 'neutral',
}

export const contactTones: Record<FollowUpContactState, StatusTone> = {
  pending: 'neutral',
  contacted: 'progress',
  confirmed: 'success',
  still_affected: 'warning',
  no_response: 'neutral',
}
