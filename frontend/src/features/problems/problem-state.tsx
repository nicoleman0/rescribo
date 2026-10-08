import type { ProblemState } from '@/api/problems'
import { StatusBadge } from '@/components/status/status-badge'
import { problemStateLabels, problemStateTones } from './problem-format'

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
