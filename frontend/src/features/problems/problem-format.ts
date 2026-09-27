import type { ProblemState } from '@/api/problems'

export const problemStateLabels: Record<ProblemState, string> = {
  open: 'Open',
  in_progress: 'In progress',
  fix_available: 'Fix available',
  not_planned: 'Not planned',
}

export const countLabel = (count: number, noun: string) =>
  `${count} ${count === 1 ? noun : `${noun}s`}`

export const reportCountLabel = (count: number) => countLabel(count, 'report')
