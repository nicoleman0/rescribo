import { createContext, useContext } from 'react'
import { cn } from '@/lib/utils'
import { problemCard } from '@/features/problems/problem-card'

export const wrapLongText = 'min-w-0 [overflow-wrap:anywhere]'
export type FollowUpLayout = 'panel' | 'page'
export const FollowUpLayoutContext = createContext<FollowUpLayout>('panel')

export function useSectionClass(gap = 'gap-3') {
  const layout = useContext(FollowUpLayoutContext)
  return layout === 'panel'
    ? `grid ${gap} rounded-card border border-border p-4`
    : cn(problemCard, gap)
}
