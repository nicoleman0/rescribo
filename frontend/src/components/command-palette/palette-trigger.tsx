import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { shortcutKeys } from '@/lib/shortcuts'

export function PaletteTrigger({ onOpen }: { onOpen: () => void }) {
  return (
    <Button
      type="button"
      variant="outline"
      aria-label="Open command palette"
      aria-keyshortcuts="Meta+K Control+K"
      onClick={onOpen}
      className="max-md:size-11 md:w-48 md:justify-between md:px-3"
    >
      <span className="flex items-center gap-2 text-muted-foreground">
        <Search aria-hidden="true" className="size-4" />
        <span className="max-md:hidden">Search</span>
      </span>
      <kbd
        aria-hidden="true"
        className="rounded-control bg-muted px-1.5 font-mono text-[11px] text-muted-foreground max-md:hidden"
      >
        {shortcutKeys('openPalette').join(' ')}
      </kbd>
    </Button>
  )
}
