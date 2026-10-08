import type { ProblemState } from '@/api/problems'
import type { StatusTone } from '@/components/status/status-tone'

export const problemStateLabels: Record<ProblemState, string> = {
  open: 'Open',
  in_progress: 'In progress',
  fix_available: 'Fix available',
  not_planned: 'Not planned',
}

export const problemStateTones: Record<ProblemState, StatusTone> = {
  open: 'info',
  in_progress: 'progress',
  fix_available: 'success',
  not_planned: 'neutral',
}

export const countLabel = (count: number, noun: string) =>
  `${count} ${count === 1 ? noun : `${noun}s`}`

export const reportCountLabel = (count: number) => countLabel(count, 'report')
