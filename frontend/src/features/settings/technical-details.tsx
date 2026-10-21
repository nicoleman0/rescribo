import type { ReactNode } from 'react'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'

export function TechnicalDetails({ children }: { children: ReactNode }) {
  return (
    <details className="text-sm">
      <summary
        className={cn('w-fit cursor-pointer rounded-control py-2', touchTarget)}
      >
        Technical details
      </summary>
      {children}
    </details>
  )
}
