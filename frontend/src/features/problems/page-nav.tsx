import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

/** Previous/next paging for a DRF page. `onPage(undefined)` means page 1. */
export function PageNav({
  label,
  count,
  page,
  pageNumber,
  onPage,
}: {
  label: string
  count: string
  page: { next?: string | null; previous?: string | null }
  pageNumber: number
  onPage: (page: number | undefined) => void
}) {
  const hasPages = Boolean(page.previous || page.next)
  return (
    <nav aria-label={label} className="flex items-center justify-between gap-3">
      <p className="font-mono text-xs text-muted-foreground" aria-live="polite">
        {count}
        {hasPages ? ` · page ${pageNumber}` : ''}
      </p>
      {hasPages ? (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!page.previous}
            onClick={() => onPage(pageNumber > 2 ? pageNumber - 1 : undefined)}
          >
            <ChevronLeft aria-hidden="true" />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!page.next}
            onClick={() => onPage(pageNumber + 1)}
          >
            Next
            <ChevronRight aria-hidden="true" />
          </Button>
        </div>
      ) : null}
    </nav>
  )
}
