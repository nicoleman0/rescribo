import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getSlackChannels } from '@/api/settings'
import type { Connection } from '@/api/settings'
import { SelectField } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/states/async-states'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'
import { useSettingsAction } from './use-settings-action'

const unavailableLabels: Record<string, string> = {
  externally_shared: 'Slack Connect, not allowed',
}

export function AllowedChannels({
  workspaceId,
  workspaceName,
  connection,
  busy,
  action,
}: {
  workspaceId: string
  workspaceName: string
  connection: Connection
  busy: boolean
  action: ReturnType<typeof useSettingsAction>
}) {
  const [channelId, setChannelId] = useState('')
  const [channelConsent, setChannelConsent] = useState(false)
  const channels = useQuery({
    queryKey: ['slack-channels', workspaceId],
    queryFn: () => getSlackChannels(workspaceId),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  })
  const existing = new Set(connection.channels.map((item) => item.channel_id))
  const options = (channels.data?.channels ?? []).filter(
    (item) => !existing.has(item.channel_id),
  )
  const hasSelectableChannel = options.some((item) => !item.unavailable_reason)
  return (
    <section className="grid gap-3" aria-labelledby="allowed-channels-heading">
      <h3 id="allowed-channels-heading" className="font-medium">
        Allowed Slack channels
      </h3>
      <p className="max-w-prose text-sm text-muted-foreground">
        Use an internal public or private channel with the bot invited. DMs and
        Slack Connect channels are not allowed. All workspace members can read
        captured reports.
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
              className="h-auto min-h-11 max-w-full py-2 text-left break-words whitespace-normal"
              disabled={busy}
              onClick={() =>
                action.mutate(
                  {
                    path: 'channels/',
                    body: {
                      version: connection.version,
                      channel_id: item.channel_id,
                      remove: true,
                    },
                  },
                  { onSuccess: () => void channels.refetch() },
                )
              }
            >
              Remove channel {item.name}
            </Button>
          </li>
        ))}
      </ul>
      {channels.isPending ? (
        <LoadingState label="Loading Slack channels" />
      ) : null}
      {channels.isError ? (
        <ErrorState
          title="Could not load Slack channels"
          description={channels.error.message}
          onRetry={() => void channels.refetch()}
          isRetrying={channels.isFetching}
        />
      ) : null}
      {channels.data && !hasSelectableChannel ? (
        <div className="grid justify-items-start gap-2">
          <p className="text-sm text-muted-foreground">
            The app is not in any other channel. In Slack, invite it to a
            channel, then load the list again.
          </p>
          <Button
            variant="outline"
            className="min-h-11"
            onClick={() => void channels.refetch()}
          >
            Refresh channel list
          </Button>
        </div>
      ) : null}
      {channels.data && options.length > 0 ? (
        <>
          {channels.data.truncated ? (
            <p className="text-sm text-muted-foreground">
              Showing the first 1,000 channels.
            </p>
          ) : null}
          <form
            className="grid max-w-lg gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              action.mutate(
                {
                  path: 'channels/',
                  body: {
                    version: connection.version,
                    channel_id: channelId,
                    consent: channelConsent,
                  },
                },
                {
                  onSuccess: () => {
                    setChannelId('')
                    setChannelConsent(false)
                    void channels.refetch()
                  },
                },
              )
            }}
          >
            <SelectField
              id="slack-channel"
              label="Slack channel"
              required
              value={channelId}
              onChange={(event) => setChannelId(event.target.value)}
              error={fieldError(action.error, 'channel_id')}
            >
              <option value="">Choose a channel</option>
              {options.map((item) => (
                <option
                  key={item.channel_id}
                  value={item.channel_id}
                  disabled={Boolean(item.unavailable_reason)}
                >
                  #{item.name} ·{' '}
                  {item.unavailable_reason
                    ? unavailableLabels[item.unavailable_reason]
                    : item.is_private
                      ? 'Private'
                      : 'Public'}
                </option>
              ))}
            </SelectField>
            <label
              className={cn(
                'flex min-h-11 items-start gap-3 text-sm',
                touchTarget,
              )}
            >
              <input
                type="checkbox"
                className="mt-1 size-4"
                checked={channelConsent}
                onChange={(event) => setChannelConsent(event.target.checked)}
              />
              Reports captured from approved channels will be visible to all
              members of {workspaceName}.
            </label>
            <Button
              className="min-h-11 w-fit"
              disabled={!channelId || !channelConsent || busy}
            >
              Allow channel
            </Button>
          </form>
          {hasSelectableChannel ? (
            <Button
              variant="outline"
              className="min-h-11 w-fit"
              onClick={() => void channels.refetch()}
            >
              Refresh channel list
            </Button>
          ) : null}
        </>
      ) : null}
      {action.error ? (
        <ErrorState
          title="Connection update failed"
          description={<FormErrorMessage error={action.error} />}
        />
      ) : null}
    </section>
  )
}
