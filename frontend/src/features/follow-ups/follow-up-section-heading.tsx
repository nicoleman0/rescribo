import { useContext, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { FollowUpLayoutContext } from './follow-up-layout'

export function SectionHeading({
  children,
  id,
  className,
}: {
  children: ReactNode
  id?: string
  className?: string
}) {
  const layout = useContext(FollowUpLayoutContext)
  const Heading = layout === 'panel' ? 'h3' : 'h2'
  return (
    <Heading id={id} className={cn('font-medium', className)}>
      {children}
    </Heading>
  )
}
