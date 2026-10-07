import type { ProblemState } from '@/api/problems'
import { StatusBadge } from '@/components/status/status-badge'
import type { StatusTone } from '@/components/status/status-tone'
import { problemStateLabels } from './problem-format'

const problemStateTones: Record<ProblemState, StatusTone> = {
  open: 'info',
  in_progress: 'progress',
  fix_available: 'success',
  not_planned: 'neutral',
}

export function ProblemStateBadge({ state }: { state: ProblemState }) {
  return (
    <StatusBadge tone={problemStateTones[state]}>
      {problemStateLabels[state]}
    </StatusBadge>
  )
}

export function NeedsReviewBadge() {
  return <StatusBadge tone="warning">Needs review</StatusBadge>
}
