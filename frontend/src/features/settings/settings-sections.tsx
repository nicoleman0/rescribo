import type { ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getConnections, settingsKey } from '@/api/settings'
import { demoDescription, useWorkspace } from '@/components/auth/use-workspace'
import { PageTitle } from '@/components/layout/page-title'
import {
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { ConfirmAction } from './confirm-action'
import { ConnectionSettings } from './connection-settings'
import { MembersSettings } from './members-settings'
import { SlackAccount } from './slack-account'
import { ThemeSettings } from './theme-settings'

function SectionTitle({ title }: { title: string }) {
  return <PageTitle title={`${title} · Settings`} />
}

export function AppearanceSection() {
  return (
    <section className="grid gap-4">
      <SectionTitle title="Appearance" />
      <ThemeSettings />
    </section>
  )
}

export function MembersSection() {
  const { workspace, role } = useWorkspace()
  return (
    <section className="grid gap-4">
      <SectionTitle title="Members" />
      {role === 'owner' ? (
        <MembersSettings workspaceId={workspace.id} />
      ) : (
        <OwnerNote />
      )}
    </section>
  )
}

export function ConnectionsSection() {
  const { workspace, role } = useWorkspace()
  const connections = useQuery({
    queryKey: [...settingsKey(workspace.id), 'connections'],
    queryFn: () => getConnections(workspace.id),
    refetchInterval: 30000,
  })
  return (
    <section className="grid gap-6">
      <SectionTitle title="Connections" />
      <h2 className="text-base font-semibold">Connections</h2>
      {workspace.is_demo ? (
        <Alert role="note">
          <AlertTitle>Integrations are disabled in the demo</AlertTitle>
          <AlertDescription>
            {demoDescription} Connecting Slack or GitHub is not available.
          </AlertDescription>
        </Alert>
      ) : null}
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
        <ReadyState className="grid gap-6">
          {(['slack', 'github'] as const).map((provider) => (
            <ConnectionSettings
              key={provider}
              workspaceId={workspace.id}
              workspaceName={workspace.name}
              owner={role === 'owner'}
              demo={workspace.is_demo}
              provider={provider}
              connection={connections.data.find(
                (item) => item.provider === provider,
              )}
            />
          ))}
        </ReadyState>
      ) : null}
    </section>
  )
}

export function SlackAccountSection() {
  const { workspace, role } = useWorkspace()
  const connections = useQuery({
    queryKey: [...settingsKey(workspace.id), 'connections'],
    queryFn: () => getConnections(workspace.id),
    refetchInterval: 30000,
  })
  return (
    <section className="grid gap-4">
      <SectionTitle title="Slack account" />
      <SlackAccount
        workspaceId={workspace.id}
        owner={role === 'owner'}
        connected={
          connections.data?.some(
            (item) => item.provider === 'slack' && item.status === 'active',
          ) ?? false
        }
        demo={workspace.is_demo}
      />
    </section>
  )
}

export function WorkspaceSection() {
  const { workspace, role } = useWorkspace()
  const cache = useQueryClient()
  const navigate = useNavigate()
  return (
    <section className="grid gap-4">
      <SectionTitle title="Workspace" />
      {role !== 'owner' ? (
        <OwnerNote />
      ) : (
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
      )}
    </section>
  )
}

export function OwnerNote() {
  return (
    <p>
      Workspace owners manage invitations, members, connections and deletion.
    </p>
  )
}

export function SettingsContent({ children }: { children: ReactNode }) {
  const { workspace } = useWorkspace()
  return (
    <div className="animate-page-enter grid w-full gap-6">
      <header>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="mt-1 text-muted-foreground">{workspace.name}</p>
      </header>
      {children}
    </div>
  )
}
