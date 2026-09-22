import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { getSession, sessionQueryKey } from '@/api/auth'
import { WorkspaceProvider } from './workspace-provider'
import { Button } from '@/components/ui/button'
import { EmptyState, LoadingState } from '@/components/states/async-states'
import { logout } from '@/api/auth'

export function RequireAuth() {
  const location = useLocation()
  const navigate = useNavigate()
  const [logoutError, setLogoutError] = useState('')
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
          <div className="grid justify-items-center gap-2">
            {logoutError ? <p role="alert">{logoutError}</p> : null}
            <Button
              onClick={async () => {
                setLogoutError('')
                try {
                  await logout()
                  queryClient.clear()
                  navigate('/sign-in', { replace: true })
                } catch (error) {
                  setLogoutError(
                    error instanceof Error ? error.message : 'Sign out failed.',
                  )
                }
              }}
            >
              Sign out
            </Button>
          </div>
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
