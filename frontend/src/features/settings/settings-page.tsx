import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getConnections, settingsKey } from '@/api/settings'
import { demoDescription, useWorkspace } from '@/components/auth/use-workspace'
import { ErrorState, LoadingState } from '@/components/states/async-states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { ConnectionSettings } from './connection-settings'
import { MembersSettings } from './members-settings'
import { SlackAccount } from './slack-account'
import { ConfirmAction } from './confirm-action'

export function SettingsPage() {
  const membership = useWorkspace()
  return <WorkspaceSettings key={membership.workspace.id} />
}

function WorkspaceSettings() {
  const { workspace, role } = useWorkspace()
  const cache = useQueryClient()
  const navigate = useNavigate()
  const connections = useQuery({
    queryKey: [...settingsKey(workspace.id), 'connections'],
    queryFn: () => getConnections(workspace.id),
    refetchInterval: 30000,
  })
  return (
    <div className="mx-auto grid w-full max-w-3xl gap-6">
      <header>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="mt-1 text-muted-foreground">{workspace.name}</p>
      </header>
      {workspace.is_demo ? (
        <Alert role="note">
          <AlertTitle>Integrations are disabled in the demo</AlertTitle>
          <AlertDescription>
            {demoDescription} Connecting Slack or GitHub is not available.
          </AlertDescription>
        </Alert>
      ) : null}
      {role === 'owner' ? (
        <MembersSettings workspaceId={workspace.id} />
      ) : (
        <p>
          Workspace owners manage invitations, members, connections and
          deletion.
        </p>
      )}
      <Separator />
      {connections.isPending ? (
        <LoadingState label="Loading connections" />
      ) : null}
      {connections.isError && !connections.data ? (
        <ErrorState
          title="Could not load connections"
          onRetry={() => void connections.refetch()}
        />
      ) : null}
      {connections.isError && connections.data ? (
        <ErrorState
          title="Could not refresh connections"
          description="Settings remain available with the last loaded values. Retry to check for updates."
          onRetry={() => void connections.refetch()}
          isRetrying={connections.isFetching}
        />
      ) : null}
      {connections.data ? (
        <>
          {(['slack', 'github'] as const).map((provider) => (
            <div className="grid gap-6" key={provider}>
              <ConnectionSettings
                workspaceId={workspace.id}
                workspaceName={workspace.name}
                owner={role === 'owner'}
                provider={provider}
                connection={connections.data.find(
                  (item) => item.provider === provider,
                )}
              />
              <Separator />
            </div>
          ))}
          <SlackAccount
            workspaceId={workspace.id}
            connected={connections.data.some(
              (item) => item.provider === 'slack' && item.status === 'active',
            )}
          />
          <Separator />
        </>
      ) : null}
      {role === 'owner' ? (
        <section className="grid gap-3" aria-labelledby="delete-heading">
          <h2 id="delete-heading" className="text-base font-semibold">
            Delete workspace
          </h2>
          <ConfirmAction
            workspaceId={workspace.id}
            path="delete/"
            phrase={workspace.slug}
            label="Delete workspace"
            scope={`Permanently delete ${workspace.name}: memberships, invitations, reports, captured snapshots, problems, notification history, activity and connection credentials. Pending sends stop. Shared user accounts and other workspaces remain. Slack messages and GitHub issues remain. Backups expire under the operator's retention policy; this does not erase backups immediately.`}
            onSuccess={() => {
              cache.clear()
              navigate('/')
            }}
          />
        </section>
      ) : null}
    </div>
  )
}
