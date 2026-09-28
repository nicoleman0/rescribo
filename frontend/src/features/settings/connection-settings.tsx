import { useState } from 'react'
import type { Connection } from '@/api/settings'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import { ErrorState } from '@/components/states/async-states'
import { ConfirmAction } from './confirm-action'
import { useSettingsAction } from './use-settings-action'

export function ConnectionSettings({
  workspaceId,
  workspaceName,
  provider,
  connection,
  owner,
}: {
  workspaceId: string
  workspaceName: string
  provider: 'slack' | 'github'
  connection?: Connection
  owner: boolean
}) {
  const [repository, setRepository] = useState(connection?.repository ?? '')
  const [channel, setChannel] = useState('')
  const [consent, setConsent] = useState(false)
  const setup = useSettingsAction<{ url: string }>(workspaceId)
  const action = useSettingsAction(workspaceId)
  const name = provider === 'slack' ? 'Slack' : 'GitHub'
  const active = connection && connection.status !== 'disconnected'
  return (
    <section className="grid gap-4" aria-labelledby={`${provider}-heading`}>
      <div className="flex flex-wrap justify-between gap-2">
        <h2 id={`${provider}-heading`} className="text-base font-semibold">
          {name}
        </h2>
        <span>{connection?.status ?? 'Not connected'}</span>
      </div>
      {connection ? (
        <>
          <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2 text-sm">
            <dt className="text-muted-foreground">Identity</dt>
            <dd className="break-words">
              {connection.identity || 'Not connected'}{' '}
              {connection.external_id ? `(${connection.external_id})` : ''}
            </dd>
            <dt className="text-muted-foreground">Scopes</dt>
            <dd className="break-words">
              {connection.scopes.join(', ') || 'None'}
            </dd>
            <dt className="text-muted-foreground">Last API success</dt>
            <dd>
              {connection.last_success_at
                ? new Date(connection.last_success_at).toLocaleString()
                : 'Never'}
            </dd>
            {provider === 'github' ? (
              <>
                <dt className="text-muted-foreground">Repository</dt>
                <dd className="break-words">
                  {connection.repository || 'None'} {connection.visibility}
                </dd>
                <dt className="text-muted-foreground">Last issue sync</dt>
                <dd>
                  {connection.last_reconciled_at
                    ? new Date(connection.last_reconciled_at).toLocaleString()
                    : 'Never'}
                </dd>
              </>
            ) : null}
          </dl>
          <p className="text-sm text-muted-foreground">
            Queued: {connection.operations.queued}. Running:{' '}
            {connection.operations.running}. Failed:{' '}
            {connection.operations.failed}. Uncertain:{' '}
            {connection.operations.uncertain}.
          </p>
          {connection.error_code ? (
            <ErrorState
              title="Connection needs attention"
              description={connection.error_detail}
            />
          ) : null}
        </>
      ) : (
        <p className="text-muted-foreground">
          {owner
            ? `Connect ${name} to this workspace.`
            : 'Ask a workspace owner to connect this application.'}
        </p>
      )}
      {owner ? (
        <>
          <form
            className="grid max-w-lg gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              setup.mutate(
                {
                  path: `connections/${provider}/setup/`,
                  body: { repository, consent },
                },
                {
                  onSuccess: (data) => {
                    window.location.assign(data.url)
                  },
                },
              )
            }}
          >
            {provider === 'github' ? (
              <Field
                id="github-repository"
                label="GitHub repository"
                placeholder="owner/repository"
                required
                value={repository}
                onChange={(event) => setRepository(event.target.value)}
                hint="Install the configured GitHub App on this repository first. Authorise a GitHub user who can access it."
                error={setup.error?.fieldErrors?.repository?.join(' ')}
              />
            ) : null}
            <label className="flex min-h-11 items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1 size-4"
                checked={consent}
                onChange={(event) => setConsent(event.target.checked)}
              />
              {provider === 'slack'
                ? `Reports captured from approved channels will be visible to all members of ${workspaceName}.`
                : 'I allow all workspace members to view linked issue metadata and create issues in the selected repository.'}
            </label>
            <Button
              className="min-h-11 w-fit"
              disabled={!consent || setup.isPending}
            >
              {active ? `Reconnect ${name}` : `Connect ${name}`}
            </Button>
          </form>
          {setup.error ? (
            <ErrorState
              title={`Could not connect ${name}`}
              description={setup.error.message}
            />
          ) : null}
          {active ? (
            <>
              <Button
                variant="outline"
                className="min-h-11 w-fit"
                disabled={action.isPending}
                onClick={() =>
                  action.mutate({
                    path: `connections/${provider}/refresh/`,
                    body: { version: connection.version },
                  })
                }
              >
                Check {name} status
              </Button>
              <ConfirmAction
                workspaceId={workspaceId}
                path={`connections/${provider}/disconnect/`}
                body={{ version: connection.version }}
                phrase="DISCONNECT"
                label={`Disconnect ${name}`}
                scope="Remove usable credentials and the installation binding, cancel pending notifications, and stop further use by this workspace. Stored reports and sent history remain. Upstream messages and issues remain. Reconnecting requires fresh notification approval."
              />
            </>
          ) : null}
          {provider === 'slack' && active ? (
            <div className="grid gap-3">
              <h3 className="font-medium">Allowed Slack channels</h3>
              <p className="max-w-prose text-sm text-muted-foreground">
                Use an internal public or private channel with the bot invited.
                DMs and Slack Connect channels are not allowed. All workspace
                members can read captured reports.
              </p>
              {connection.channels.length === 0 ? (
                <p>No channels allowed yet.</p>
              ) : null}
              <ul className="grid gap-3">
                {connection.channels.map((item) => (
                  <li
                    key={item.channel_id}
                    className="flex flex-wrap items-center justify-between gap-2"
                  >
                    <span className="break-all">
                      #{item.name} ({item.channel_id}) ·{' '}
                      {item.is_private ? 'Private' : 'Public'}
                    </span>
                    <Button
                      variant="outline"
                      className="min-h-11"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate({
                          path: 'channels/',
                          body: {
                            version: connection.version,
                            channel_id: item.channel_id,
                            remove: true,
                          },
                        })
                      }
                    >
                      Remove channel {item.name}
                    </Button>
                  </li>
                ))}
              </ul>
              <form
                className="grid max-w-lg gap-3"
                onSubmit={(event) => {
                  event.preventDefault()
                  action.mutate(
                    {
                      path: 'channels/',
                      body: {
                        version: connection.version,
                        channel_id: channel,
                        consent,
                      },
                    },
                    { onSuccess: () => setChannel('') },
                  )
                }}
              >
                <Field
                  id="channel-id"
                  label="Slack channel ID"
                  required
                  value={channel}
                  onChange={(event) => setChannel(event.target.value)}
                  error={action.error?.fieldErrors?.channel_id?.join(' ')}
                  hint="Confirm workspace visibility above before allowing a channel."
                />
                <Button
                  className="min-h-11 w-fit"
                  disabled={!consent || action.isPending}
                >
                  Validate and allow channel
                </Button>
              </form>
            </div>
          ) : null}
          {action.error ? (
            <ErrorState
              title="Connection update failed"
              description={action.error.message}
            />
          ) : null}
        </>
      ) : null}
    </section>
  )
}
