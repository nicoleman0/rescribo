import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getModelDeployment,
  settingsKey,
  type Connection,
  type ModelConnect,
} from '@/api/settings'
import { formatDate } from '@/features/inbox/report-format'
import { Field, SelectField } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardHeader } from '@/components/ui/card'
import { ErrorState } from '@/components/states/async-states'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'
import { ConfirmAction } from './confirm-action'
import { CheckResult } from './connection-settings'
import { ConnectionStatusBadge } from './connection-status'
import { TechnicalDetails } from './technical-details'
import { useSettingsAction } from './use-settings-action'

type ApiStyle = 'openai' | 'anthropic'

// The backend stores only the API style and base URL; a preset is a shortcut to both.
const modelPresets = [
  {
    id: 'openai',
    label: 'OpenAI',
    apiStyle: 'openai',
    baseUrl: 'https://api.openai.com/v1',
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    apiStyle: 'anthropic',
    baseUrl: 'https://api.anthropic.com',
  },
  {
    id: 'google',
    label: 'Google',
    apiStyle: 'openai',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
  },
  {
    id: 'openrouter',
    label: 'OpenRouter',
    apiStyle: 'openai',
    baseUrl: 'https://openrouter.ai/api/v1',
  },
  {
    id: 'other',
    label: 'Other OpenAI-compatible',
    apiStyle: 'openai',
    baseUrl: '',
  },
] as const satisfies readonly {
  id: string
  label: string
  apiStyle: ApiStyle
  baseUrl: string
}[]

type PresetId = (typeof modelPresets)[number]['id']

const styleLabels: Record<string, string> = {
  openai: 'OpenAI-compatible',
  anthropic: 'Anthropic',
}

function presetFor(connection?: Connection): PresetId {
  if (!connection?.base_url) return 'openai'
  return (
    modelPresets.find(
      (preset) =>
        preset.baseUrl === connection.base_url &&
        preset.apiStyle === connection.api_style,
    )?.id ?? 'other'
  )
}

export function ModelProviderSettings({
  workspaceId,
  workspaceName,
  connection,
  owner,
  demo,
}: {
  workspaceId: string
  workspaceName: string
  connection?: Connection
  owner: boolean
  demo: boolean
}) {
  const deployment = useQuery({
    queryKey: [...settingsKey(workspaceId), 'model-deployment'],
    queryFn: () => getModelDeployment(workspaceId),
  })
  const managed = deployment.data?.managed ?? false
  const active = connection && connection.status !== 'disconnected'
  const action = useSettingsAction(workspaceId)
  const check = useSettingsAction(workspaceId)
  const values = managed ? deployment.data : active ? connection : undefined
  return (
    <section aria-labelledby="model-heading">
      <Card>
        <CardHeader>
          <h2 id="model-heading" className="text-base font-semibold">
            Model provider
          </h2>
          <CardAction>
            <ConnectionStatusBadge status={connection?.status} demo={demo} />
          </CardAction>
        </CardHeader>
        <CardContent className="grid gap-4">
          {managed ? (
            <p className="text-muted-foreground">
              This deployment sets the model provider. Its values cannot be
              changed here.
            </p>
          ) : null}
          {values ? (
            <dl className="grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted-foreground">API style</dt>
              <dd>{styleLabels[values.api_style] ?? values.api_style}</dd>
              <dt className="text-muted-foreground">Base URL</dt>
              <dd className="break-words">{values.base_url}</dd>
              <dt className="text-muted-foreground">Model</dt>
              <dd className="break-words">{values.model}</dd>
              {connection ? (
                <>
                  <dt className="text-muted-foreground">Last reached</dt>
                  <dd>
                    {connection.last_success_at
                      ? formatDate(connection.last_success_at)
                      : 'Not yet'}
                  </dd>
                </>
              ) : null}
            </dl>
          ) : (
            <p className="text-muted-foreground">
              {owner
                ? 'Connect a language model so Rescribo can draft from conversations.'
                : 'Ask a workspace owner to connect a model provider.'}
            </p>
          )}
          {owner && connection?.error_code ? (
            <TechnicalDetails>
              <dl className="mt-2 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-3 gap-y-2">
                <dt className="text-muted-foreground">Error code</dt>
                <dd className="break-words font-mono">
                  {connection.error_code}
                </dd>
              </dl>
            </TechnicalDetails>
          ) : null}
          {connection?.error_code ? (
            <ErrorState
              title="Connection needs attention"
              description={connection.error_detail}
            />
          ) : null}
          {owner && deployment.data ? (
            <ModelProviderForm
              key={managed ? 'managed' : 'settings'}
              workspaceId={workspaceId}
              workspaceName={workspaceName}
              connection={active ? connection : undefined}
              managed={managed}
            />
          ) : null}
          {owner && deployment.isError ? (
            <ErrorState
              title="Could not load the deployment settings"
              onRetry={() => void deployment.refetch()}
            />
          ) : null}
          {owner && active ? (
            <>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <Button
                  variant="outline"
                  className="min-h-11 w-fit"
                  disabled={check.isPending || action.isPending}
                  onClick={() =>
                    check.mutate({
                      path: 'connections/model/refresh/',
                      body: { version: connection.version },
                    })
                  }
                >
                  Check model provider status
                </Button>
                <CheckResult
                  name="Model provider"
                  check={check}
                  working={connection.status === 'active'}
                />
              </div>
              <ConfirmAction
                workspaceId={workspaceId}
                path="connections/model/disconnect/"
                body={{ version: connection.version }}
                phrase="DISCONNECT"
                label="Disconnect model provider"
                scope="Delete the stored API key and this workspace's consent, and stop model use by this workspace. Reports and other records remain. Reconnecting asks for consent again."
              />
            </>
          ) : null}
        </CardContent>
      </Card>
    </section>
  )
}

function ModelProviderForm({
  workspaceId,
  workspaceName,
  connection,
  managed,
}: {
  workspaceId: string
  workspaceName: string
  connection?: Connection
  managed: boolean
}) {
  const [preset, setPreset] = useState<PresetId>(presetFor(connection))
  const [baseUrl, setBaseUrl] = useState(
    connection?.base_url ?? modelPresets[0].baseUrl,
  )
  const [model, setModel] = useState(connection?.model ?? '')
  const [apiKey, setApiKey] = useState('')
  const [consent, setConsent] = useState(false)
  const connect = useSettingsAction(workspaceId)
  const apiStyle = modelPresets.find((item) => item.id === preset)!.apiStyle
  // Omitted fields default to blank, which the deployment config requires.
  const body: Partial<ModelConnect> = managed
    ? { consent }
    : {
        api_style: apiStyle,
        base_url: baseUrl,
        model,
        api_key: apiKey,
        consent,
      }
  return (
    <>
      <form
        className="grid max-w-lg gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          connect.mutate(
            { path: 'connections/model/connect/', body },
            // The key never stays in the page, pass or fail.
            { onSettled: () => setApiKey('') },
          )
        }}
      >
        {managed ? null : (
          <>
            <SelectField
              id="model-provider"
              label="Provider"
              value={preset}
              onChange={(event) => {
                const next = modelPresets.find(
                  (item) => item.id === event.target.value,
                )!
                setPreset(next.id)
                setBaseUrl(next.baseUrl)
              }}
            >
              {modelPresets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </SelectField>
            <Field
              id="model-base-url"
              label="Base URL"
              type="url"
              required
              placeholder="https://"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              hint="Public HTTPS only. Ask the operator to configure a local or private server."
              error={fieldError(connect.error, 'base_url')}
            />
            <Field
              id="model-name"
              label="Model"
              required
              value={model}
              onChange={(event) => setModel(event.target.value)}
              error={fieldError(connect.error, 'model')}
            />
            <Field
              id="model-api-key"
              label="API key"
              type="password"
              autoComplete="off"
              required={!connection}
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              hint={
                connection
                  ? 'Leave blank to keep the stored key. A new base URL or provider needs a new key.'
                  : undefined
              }
              error={fieldError(connect.error, 'api_key')}
            />
          </>
        )}
        <label
          className={cn('flex min-h-11 items-start gap-3 text-sm', touchTarget)}
        >
          <input
            type="checkbox"
            className="mt-1 size-4"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />
          {`Conversation and report content from ${workspaceName} will be sent to this model provider.`}
        </label>
        <Button
          className="min-h-11 w-fit"
          disabled={!consent || connect.isPending}
        >
          {connect.isPending
            ? 'Testing connection…'
            : managed
              ? 'Enable model provider'
              : connection
                ? 'Save and test'
                : 'Connect model provider'}
        </Button>
      </form>
      {connect.error ? (
        <ErrorState
          title="Could not connect the model provider"
          description={<FormErrorMessage error={connect.error} />}
        />
      ) : null}
    </>
  )
}
