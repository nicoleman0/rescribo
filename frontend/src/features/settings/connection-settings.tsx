import { useState } from 'react'
import type { Connection } from '@/api/settings'
import { formatDate } from '@/features/inbox/report-format'
import { Field } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { ErrorState } from '@/components/states/async-states'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'
import { ConfirmAction } from './confirm-action'
import { ConnectionStatusBadge } from './connection-status'
import { useSettingsAction } from './use-settings-action'
import { AllowedChannels } from './allowed-channels'
import { TechnicalDetails } from './technical-details'

export function ConnectionSettings({
  workspaceId,
  workspaceName,
  provider,
  connection,
  owner,
  demo,
}: {
  workspaceId: string
  workspaceName: string
  provider: 'slack' | 'github'
  connection?: Connection
  owner: boolean
  demo: boolean
}) {
  const [repository, setRepository] = useState(connection?.repository ?? '')
  const [consent, setConsent] = useState(false)
  const setup = useSettingsAction<{ url: string }>(workspaceId)
  const action = useSettingsAction(workspaceId)
  // Its own mutation, so a channel save is never read as a passed check.
  const check = useSettingsAction(workspaceId)
  const busy = check.isPending || action.isPending
  const name = provider === 'slack' ? 'Slack' : 'GitHub'
  const active = connection && connection.status !== 'disconnected'
  return (
    <section aria-labelledby={`${provider}-heading`}>
      <Card>
        <CardHeader>
          <h2 id={`${provider}-heading`} className="text-base font-semibold">
            {name}
          </h2>
          <CardAction>
            <ConnectionStatusBadge status={connection?.status} demo={demo} />
          </CardAction>
        </CardHeader>
        <CardContent className="grid gap-4">
          {connection ? (
            <>
              <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
                <dt className="text-muted-foreground">
                  {provider === 'slack' ? 'Slack workspace' : 'GitHub account'}
                </dt>
                <dd className="break-words">
                  {connection.identity || 'Not connected'}
                </dd>
                {provider === 'github' ? (
                  <>
                    <dt className="text-muted-foreground">Repository</dt>
                    <dd className="break-words">
                      {connection.repository || 'None'}
                      {connection.visibility ? (
                        <span className="ml-1.5 text-muted-foreground">
                          {connection.visibility === 'private'
                            ? 'Private'
                            : 'Public'}
                        </span>
                      ) : null}
                    </dd>
                  </>
                ) : null}
                <dt className="text-muted-foreground">Last reached {name}</dt>
                <dd>
                  {connection.last_success_at
                    ? formatDate(connection.last_success_at)
                    : 'Not yet'}
                </dd>
                {provider === 'github' ? (
                  <>
                    <dt className="text-muted-foreground">
                      Issues last synced
                    </dt>
                    <dd>
                      {connection.last_reconciled_at
                        ? formatDate(connection.last_reconciled_at)
                        : 'Not yet'}
                    </dd>
                  </>
                ) : null}
              </dl>
              {owner ? (
                <TechnicalDetails>
                  <dl className="mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2">
                    <dt className="text-muted-foreground">Provider ID</dt>
                    <dd className="break-words font-mono">
                      {connection.external_id || 'None'}
                    </dd>
                    <dt className="text-muted-foreground">Scopes</dt>
                    <dd className="break-words font-mono">
                      {connection.scopes.join(', ') || 'None'}
                    </dd>
                    <dt className="text-muted-foreground">Last API success</dt>
                    <dd>
                      {connection.last_success_at
                        ? formatDate(connection.last_success_at)
                        : 'None'}
                    </dd>
                    {provider === 'github' ? (
                      <>
                        <dt className="text-muted-foreground">
                          Last issue sync
                        </dt>
                        <dd>
                          {connection.last_reconciled_at
                            ? formatDate(connection.last_reconciled_at)
                            : 'None'}
                        </dd>
                      </>
                    ) : null}
                    <dt className="text-muted-foreground">Error code</dt>
                    <dd className="break-words font-mono">
                      {connection.error_code || 'None'}
                    </dd>
                  </dl>
                </TechnicalDetails>
              ) : null}
              <JobCounts provider={name} operations={connection.operations} />
              {connection.error_code ? (
                <ErrorState
                  title="Connection needs attention"
                  description={connection.error_detail}
                />
              ) : null}
              {provider === 'slack' &&
              connection.status === 'active' &&
              owner &&
              !demo ? (
                <AllowedChannels
                  workspaceId={workspaceId}
                  workspaceName={workspaceName}
                  connection={connection}
                  busy={busy}
                  action={action}
                />
              ) : null}
              {provider === 'slack' &&
              connection.status === 'active' &&
              owner &&
              !demo ? (
                <Separator />
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
                      // The API rejects a blank repository, and Slack has none.
                      body:
                        provider === 'github'
                          ? { repository, consent }
                          : { consent },
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
                    error={fieldError(setup.error, 'repository')}
                  />
                ) : null}
                <label
                  className={cn(
                    'flex min-h-11 items-start gap-3 text-sm',
                    touchTarget,
                  )}
                >
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
                  description={<FormErrorMessage error={setup.error} />}
                />
              ) : null}
              {active ? (
                <>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <Button
                      variant="outline"
                      className="min-h-11 w-fit"
                      disabled={busy}
                      onClick={() =>
                        check.mutate({
                          path: `connections/${provider}/refresh/`,
                          body: { version: connection.version },
                        })
                      }
                    >
                      Check {name} status
                    </Button>
                    <CheckResult
                      name={name}
                      check={check}
                      working={connection.status === 'active'}
                    />
                  </div>
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
            </>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}

// Seconds, so two checks in the same minute differ.
const checkTime = new Intl.DateTimeFormat(undefined, { timeStyle: 'medium' })

export function CheckResult({
  name,
  check,
  working,
}: {
  name: string
  check: ReturnType<typeof useSettingsAction>
  working: boolean
}) {
  // The server answers a pass with no body, so the press time stands in.
  const at = new Date(check.submittedAt)
  const time = (
    <time dateTime={at.toISOString()} className="text-muted-foreground">
      {checkTime.format(at)}
    </time>
  )
  return (
    <>
      {/* Stays mounted so a screen reader announces the text change. */}
      <p role="status" className="text-sm empty:hidden">
        {check.isPending ? `Checking ${name}…` : null}
        {check.isSuccess && working ? (
          <>
            {name} connection is working. Checked at {time}.
          </>
        ) : null}
      </p>
      {check.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {name} check failed at {time}. {check.error.message}
        </p>
      ) : null}
    </>
  )
}

const jobStates = [
  ['queued', 'Queued'],
  ['running', 'Running'],
  ['failed', 'Failed'],
  ['uncertain', 'Uncertain'],
] as const

function JobCounts({
  provider,
  operations,
}: {
  provider: string
  operations: Connection['operations']
}) {
  const id = `${provider.toLowerCase()}-jobs-heading`
  return (
    <div role="group" aria-labelledby={id} className="grid gap-2">
      <h3 id={id} className="text-sm font-medium">
        Jobs
      </h3>
      <dl className="grid grid-cols-4 divide-x divide-border rounded-control border border-border">
        {jobStates.map(([key, label]) => (
          // Number above its label, with the term first for screen readers.
          <div key={key} className="flex flex-col-reverse gap-0.5 px-3 py-2">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="font-mono text-base tabular-nums">
              {operations[key]}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}
