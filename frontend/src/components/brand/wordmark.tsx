import wordmarkUrl from '@/assets/brand/wordmark.svg'
import { cn } from '@/lib/utils'

export function Wordmark({ className }: { className?: string }) {
  return (
    <img
      src={wordmarkUrl}
      alt="rescribo"
      className={cn('h-6 w-auto', className)}
    />
  )
}
