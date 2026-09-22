import type { ReactNode } from 'react'
import type { Session } from '@/api/auth'
import { WorkspaceContext } from './workspace-context'

export function WorkspaceProvider({
  children,
  membership,
}: {
  children: ReactNode
  membership: Session['memberships'][number]
}) {
  return (
    <WorkspaceContext.Provider value={membership}>
      {children}
    </WorkspaceContext.Provider>
  )
}
