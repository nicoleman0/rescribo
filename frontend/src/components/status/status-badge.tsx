import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { StatusTone } from './status-tone'

// Literal class strings so Tailwind can find them.
const toneClasses: Record<StatusTone, { badge: string; dot: string }> = {
  neutral: {
    badge: 'bg-tone-neutral text-tone-neutral-foreground',
    dot: 'bg-tone-neutral-dot',
  },
  info: {
    badge: 'bg-tone-info text-tone-info-foreground',
    dot: 'bg-tone-info-dot',
  },
  progress: {
    badge: 'bg-tone-progress text-tone-progress-foreground',
    dot: 'bg-tone-progress-dot',
  },
  success: {
    badge: 'bg-tone-success text-tone-success-foreground',
    dot: 'bg-tone-success-dot',
  },
  warning: {
    badge: 'bg-tone-warning text-tone-warning-foreground',
    dot: 'bg-tone-warning-dot',
  },
  danger: {
    badge: 'bg-tone-danger text-tone-danger-foreground',
    dot: 'bg-tone-danger-dot',
  },
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
        toneClasses[tone].badge,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn('size-1.5 rounded-pill', toneClasses[tone].dot)}
      />
      {children}
    </span>
  )
}
