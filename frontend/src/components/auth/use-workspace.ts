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

export const demoDescription =
  'Fictitious data. Nothing is sent to Slack or GitHub.'

/** Demo workspaces hold fictitious data and never reach Slack or GitHub. */
export function useIsDemo() {
  return useContext(WorkspaceContext)?.workspace.is_demo === true
}
