import type { TriageState } from '@/api/reports'
import { Badge } from '@/components/ui/badge'
import { triageLabels } from './inbox-query'

const triageClasses: Record<TriageState, string> = {
  new: 'bg-primary text-primary-foreground',
  linked: 'bg-linked text-linked-foreground',
  dismissed: 'bg-muted text-muted-foreground',
}

export function TriageBadge({ state }: { state: TriageState }) {
  return <Badge className={triageClasses[state]}>{triageLabels[state]}</Badge>
}
