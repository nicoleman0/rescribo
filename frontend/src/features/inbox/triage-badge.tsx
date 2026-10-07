import type { TriageState } from '@/api/reports'
import { StatusBadge } from '@/components/status/status-badge'
import type { StatusTone } from '@/components/status/status-tone'
import { triageLabels } from './inbox-query'

const triageTones: Record<TriageState, StatusTone> = {
  new: 'info',
  linked: 'success',
  dismissed: 'neutral',
}

export function TriageBadge({ state }: { state: TriageState }) {
  return (
    <StatusBadge tone={triageTones[state]}>{triageLabels[state]}</StatusBadge>
  )
}
