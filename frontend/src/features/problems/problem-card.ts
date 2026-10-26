import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'

// Side-column cards rest on the page, so they take elevation level 1.
export const problemCard =
  'grid gap-3 rounded-card bg-card p-4 text-sm shadow-elevation-1'
export const problemCardHeading = 'text-sm font-semibold'
// For links not inside a sentence. inline-flex lets min-height apply and centres the text.
export const standaloneLink = cn('inline-flex items-center', touchTarget)
