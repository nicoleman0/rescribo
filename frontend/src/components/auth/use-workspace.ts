import { useContext } from 'react'
import { WorkspaceContext } from './workspace-context'

export function useWorkspace() {
  const workspace = useContext(WorkspaceContext)
  if (!workspace) throw new Error('WorkspaceProvider is missing.')
  return workspace
}

export function useOptionalWorkspace() {
  return useContext(WorkspaceContext)
}
