import { useQuery } from '@tanstack/react-query'
import {
  getSlackIdentity,
  settingsKey,
  type SlackLinkCode,
} from '@/api/settings'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import {
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { useSettingsAction } from './use-settings-action'

/** The signed-in member's own Slack link. Slack redeems the code, never this page. */
export function SlackAccount({
  workspaceId,
  connected,
}: {
  workspaceId: string
  connected: boolean
}) {
  const issue = useSettingsAction<SlackLinkCode>(workspaceId)
  const identity = useQuery({
    queryKey: [...settingsKey(workspaceId), 'slack-identity'],
    queryFn: () => getSlackIdentity(workspaceId),
    // Linking finishes in Slack, so poll briefly while a code is outstanding.
    refetchInterval: (query) =>
      issue.data && !query.state.data?.linked ? 5000 : false,
  })
  const unlink = useSettingsAction(workspaceId)
  return (
    <section className="grid gap-4" aria-labelledby="slack-account-heading">
      <h2 id="slack-account-heading" className="text-base font-semibold">
        Your Slack account
      </h2>
      {identity.isPending ? (
        <LoadingState label="Loading Slack account" />
      ) : null}
      {identity.isError ? (
        <ErrorState
          title="Could not load your Slack account"
          onRetry={() => void identity.refetch()}
        />
      ) : null}
      {identity.data ? (
        <ReadyState className="grid gap-4">
          {identity.data.linked ? (
            <>
              <p className="text-sm">
                Linked to Slack user{' '}
                <span className="font-mono">{identity.data.user_id}</span> in
                team <span className="font-mono">{identity.data.team_id}</span>.
              </p>
              <Button
                variant="outline"
                className="min-h-11 w-fit"
                disabled={unlink.isPending}
                onClick={() =>
                  unlink.mutate({ path: 'slack/identity/unlink/', body: {} })
                }
              >
                Unlink Slack account
              </Button>
            </>
          ) : null}
          {identity.data && !identity.data.linked ? (
            <>
              <p className="text-sm text-muted-foreground">
                {connected
                  ? 'Link your Slack account to capture reports from Slack. Generate a code, run "Submit customer feedback" on a message in Slack, and paste the code when asked.'
                  : 'Slack is not connected to this workspace. You can link your account once an owner connects it.'}
              </p>
              {connected ? (
                <Button
                  className="min-h-11 w-fit"
                  disabled={issue.isPending}
                  onClick={() =>
                    issue.mutate({ path: 'slack/link-code/', body: {} })
                  }
                >
                  {issue.data ? 'Generate a new code' : 'Generate linking code'}
                </Button>
              ) : null}
              {issue.data ? (
                <Field
                  id="slack-link-code"
                  label="Linking code"
                  readOnly
                  className="font-mono"
                  value={issue.data.code}
                  onFocus={(event) => event.target.select()}
                  hint={`Single use. Expires at ${new Date(issue.data.expires_at).toLocaleTimeString()}.`}
                />
              ) : null}
            </>
          ) : null}
        </ReadyState>
      ) : null}
      {issue.error ? (
        <ErrorState
          title="Could not generate a code"
          description={issue.error.message}
        />
      ) : null}
      {unlink.error ? (
        <ErrorState
          title="Could not unlink your Slack account"
          description={unlink.error.message}
        />
      ) : null}
    </section>
  )
}
