import * as React from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

function NativeSelect({ className, ...props }: React.ComponentProps<'select'>) {
  return (
    <div className="relative">
      <select
        data-slot="native-select"
        className={cn(
          'h-10 w-full appearance-none rounded-control border border-input bg-background pr-8 pl-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 aria-invalid:border-destructive',
          className,
        )}
        {...props}
      />
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted-foreground"
      />
    </div>
  )
}

export { NativeSelect }
