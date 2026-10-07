import wordmarkUrl from '@/assets/brand/wordmark.svg'
import { cn } from '@/lib/utils'

// The SVG is a mask so the letterforms take their colour from the theme.
// The aspect ratio matches its viewBox.
export function Wordmark({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="rescribo"
      className={cn(
        'block aspect-[3724/819] h-6 bg-primary mask-contain mask-center mask-no-repeat forced-color-adjust-none forced-colors:bg-[CanvasText]',
        className,
      )}
      style={{ maskImage: `url(${wordmarkUrl})` }}
    />
  )
}
