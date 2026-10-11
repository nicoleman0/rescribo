import type { ProblemListItem, ProblemState } from '@/api/problems'
import { StatusBadge } from '@/components/status/status-badge'
import { problemStateLabels, problemStateTones } from './problem-format'

export function ProblemStateBadge({ state }: { state: ProblemState }) {
  return (
    <StatusBadge tone={problemStateTones[state]}>
      {problemStateLabels[state]}
    </StatusBadge>
  )
}

export function NoReportsBadge({
  problem,
}: {
  problem: Pick<ProblemListItem, 'state' | 'report_count'>
}) {
  // Settled problems need no attention when their reports are gone.
  if (
    (problem.state !== 'open' && problem.state !== 'in_progress') ||
    problem.report_count !== 0
  ) {
    return null
  }

  return <StatusBadge tone="warning">No reports</StatusBadge>
}

export function NeedsReviewBadge() {
  return <StatusBadge tone="warning">Needs review</StatusBadge>
}
