import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getSession, sessionQueryKey } from '@/api/auth'
import { WorkspaceProvider } from './workspace-provider'
import { Button } from '@/components/ui/button'
import { EmptyState, LoadingState } from '@/components/states/async-states'
import { logout } from '@/api/auth'

export function RequireAuth() {
  const location = useLocation()
  const queryClient = useQueryClient()
  const session = useQuery({
    queryKey: sessionQueryKey,
    queryFn: getSession,
    retry: false,
  })
  if (session.isPending) return <LoadingState label="Checking session" />
  if (session.isError)
    return <Navigate to="/sign-in" replace state={{ from: location }} />
  if (!session.data.memberships.length) {
    return (
      <EmptyState
        title="Workspace access removed"
        description="You no longer have access to a workspace. Sign out to finish."
        action={
          <Button
            onClick={async () => {
              await logout()
              queryClient.clear()
            }}
          >
            Sign out
          </Button>
        }
      />
    )
  }
  return (
    <WorkspaceProvider membership={session.data.memberships[0]}>
      <Outlet />
    </WorkspaceProvider>
  )
}
