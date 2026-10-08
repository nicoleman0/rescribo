import type {
  FollowUpContactState,
  FollowUpNotificationState,
} from '@/api/follow-ups'
import { useIsDemo } from '@/components/auth/use-workspace'
import { StatusBadge } from '@/components/status/status-badge'
import { cn } from '@/lib/utils'
import {
  contactStateLabels,
  contactTones,
  deliveryLabel,
  deliveryTones,
  notPreparedLabel,
  notPreparedTone,
} from './follow-ups-format'

// Rows stack the two statuses from md up so the badges line up from row to
// row; the terms are the same in every row, so the auto column is too.
const layouts = {
  inline: { list: 'flex flex-wrap', pair: '' },
  row: {
    list: 'flex flex-wrap md:grid md:grid-cols-[auto_minmax(0,1fr)] md:gap-x-3 md:gap-y-1.5',
    pair: 'md:contents',
  },
}

export function FollowUpStatuses({
  delivery,
  outcome,
  layout = 'inline',
}: {
  delivery: FollowUpNotificationState | null
  outcome: FollowUpContactState
  layout?: keyof typeof layouts
}) {
  const isDemo = useIsDemo()
  return (
    <dl
      className={cn(
        'items-center gap-x-4 gap-y-1 text-xs',
        layouts[layout].list,
      )}
    >
      <div className={cn('flex items-center gap-1.5', layouts[layout].pair)}>
        <dt className="text-muted-foreground">Delivery</dt>
        <dd>
          {delivery ? (
            <StatusBadge tone={deliveryTones[delivery]}>
              {deliveryLabel(delivery, isDemo)}
            </StatusBadge>
          ) : (
            <StatusBadge tone={notPreparedTone}>{notPreparedLabel}</StatusBadge>
          )}
        </dd>
      </div>
      <div className={cn('flex items-center gap-1.5', layouts[layout].pair)}>
        <dt className="text-muted-foreground">Outcome</dt>
        <dd>
          <StatusBadge tone={contactTones[outcome]}>
            {contactStateLabels[outcome]}
          </StatusBadge>
        </dd>
      </div>
    </dl>
  )
}
