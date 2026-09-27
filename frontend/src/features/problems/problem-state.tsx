import type { ProblemState } from '@/api/problems'
import { Badge } from '@/components/ui/badge'
import { problemStateLabels } from './problem-format'

const stateClasses: Record<ProblemState, string> = {
  open: 'bg-primary text-primary-foreground',
  in_progress: 'bg-selected text-foreground',
  fix_available: 'bg-linked text-linked-foreground',
  not_planned: 'bg-muted text-muted-foreground',
}

export function ProblemStateBadge({ state }: { state: ProblemState }) {
  return (
    <Badge className={stateClasses[state]}>{problemStateLabels[state]}</Badge>
  )
}

export function NeedsReviewBadge() {
  return (
    <Badge className="bg-needs-review text-needs-review-foreground">
      Needs review
    </Badge>
  )
}
