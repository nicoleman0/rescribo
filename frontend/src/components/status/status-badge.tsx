import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { toneSurfaceClasses, type StatusTone } from './status-tone'

// Literal class strings so Tailwind can find them.
const dotClasses: Record<StatusTone, string> = {
  neutral: 'bg-tone-neutral-dot',
  info: 'bg-tone-info-dot',
  progress: 'bg-tone-progress-dot',
  success: 'bg-tone-success-dot',
  warning: 'bg-tone-warning-dot',
  danger: 'bg-tone-danger-dot',
}

export function StatusBadge({
  tone,
  className,
  children,
}: {
  tone: StatusTone
  className?: string
  children: ReactNode
}) {
  return (
    <span
      data-slot="status-badge"
      data-tone={tone}
      className={cn(
        'inline-flex h-5 w-fit shrink-0 items-center gap-1.5 rounded-pill px-2 text-xs font-medium whitespace-nowrap',
        toneSurfaceClasses[tone],
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn('size-1.5 rounded-pill', dotClasses[tone])}
      />
      {children}
    </span>
  )
}
