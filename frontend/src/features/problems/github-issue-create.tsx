import { useEffect, useId, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getProblem, problemKeys, type ProblemDetail } from '@/api/problems'
import {
  approveGitHubIssue,
  getGitHubOperation,
  previewGitHubIssue,
  reconcileGitHubOperation,
  type IssuePreview,
} from '@/api/github-issues'
import type { ApiError } from '@/api/request'
import { Field, TextareaField } from '@/components/forms/field'
import { touchTarget } from '@/components/layout/touch-target'
import { ActionError } from '@/components/states/action-error'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { applyProblem } from '@/api/cache'
import { Link } from 'react-router-dom'

export function GitHubIssueCreate({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const id = useId()
  const client = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(problem.title)
  const [body, setBody] = useState('')
  const [previewed, setPreviewed] = useState(false)
  const [draft, setDraft] = useState<IssuePreview | null>(null)
  const [operationId, setOperationId] = useState(
    problem.current_create_operation?.id ?? '',
  )
  const [recoveryReference, setRecoveryReference] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const operation = useQuery({
    queryKey: [
      'workspaces',
      workspaceId,
      'problems',
      problem.id,
      'github-operation',
      operationId,
    ],
    queryFn: () => getGitHubOperation(workspaceId, problem.id, operationId),
    enabled: Boolean(operationId),
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.state ?? '')
        ? 2000
        : false,
    refetchIntervalInBackground: false,
  })

  useEffect(() => {
    if (operation.data?.state !== 'succeeded') return
    void getProblem(workspaceId, problem.id).then((latest) => {
      applyProblem(client, workspaceId, latest)
      void client.invalidateQueries({ queryKey: problemKeys.all(workspaceId) })
    })
  }, [client, operation.data?.state, problem.id, workspaceId])

  async function begin() {
    setBusy(true)
    setError(null)
    try {
      const result = await previewGitHubIssue(workspaceId, problem.id, {
        expected_version: problem.version,
      })
      setDraft(result)
      setTitle(result.title)
      setBody(
        result.body
          .replace(/\n?<!-- rescribo-operation:[^>]+ -->/g, '')
          .trimEnd(),
      )
      setPreviewed(false)
      setEditing(true)
    } catch (cause) {
      setError(cause as ApiError)
    } finally {
      setBusy(false)
    }
  }

  async function showPreview(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await previewGitHubIssue(workspaceId, problem.id, {
        expected_version: problem.version,
        title,
        body: body
          .replace(/\n?<!-- rescribo-operation:[^>]+ -->/g, '')
          .trimEnd(),
      })
      setDraft(result)
      setTitle(result.title)
      setBody(
        result.body
          .replace(/\n?<!-- rescribo-operation:[^>]+ -->/g, '')
          .trimEnd(),
      )
      setPreviewed(true)
    } catch (cause) {
      setError(cause as ApiError)
    } finally {
      setBusy(false)
    }
  }

  async function publish() {
    setBusy(true)
    setError(null)
    try {
      const started = await approveGitHubIssue(workspaceId, problem.id, {
        draft_id: draft!.id,
        draft_version: draft!.draft_version,
        approved: true,
      })
      setOperationId(started.id)
      setEditing(false)
    } catch (cause) {
      const apiError = cause as ApiError
      if (apiError.current)
        applyProblem(client, workspaceId, apiError.current as ProblemDetail)
      setError(apiError)
    } finally {
      setBusy(false)
    }
  }

  async function checkResult(reference?: string) {
    if (!operationId) return
    setBusy(true)
    setError(null)
    try {
      await reconcileGitHubOperation(
        workspaceId,
        problem.id,
        operationId,
        reference,
      )
      void operation.refetch()
    } catch (cause) {
      setError(cause as ApiError)
    } finally {
      setBusy(false)
    }
  }

  if (operationId && operation.data) {
    if (operation.data.state === 'succeeded') {
      return (
        <div role="status" className="grid justify-items-start gap-2">
          <p className="font-medium">GitHub issue created.</p>
          {operation.data.remote_url ? (
            <a
              className="text-sm text-primary underline"
              href={operation.data.remote_url}
              target="_blank"
              rel="noreferrer"
            >
              Open issue #{operation.data.remote_number}
            </a>
          ) : null}
        </div>
      )
    }
    if (operation.data.state === 'uncertain') {
      return (
        <div className="grid gap-3" aria-live="polite">
          <p className="font-medium">
            GitHub may have created this issue. Check the result before taking
            another action.
          </p>
          <Field
            id={`${id}-recovery-reference`}
            label="Existing issue reference (optional)"
            hint="Use this if the issue exists but automatic recovery did not find it. It must contain the operation marker."
            value={recoveryReference}
            onChange={(event) => setRecoveryReference(event.target.value)}
          />
          <div className="flex flex-wrap gap-2">
            <Button
              className={touchTarget}
              disabled={busy}
              onClick={() => void checkResult(recoveryReference || undefined)}
            >
              {busy ? 'Checking…' : 'Check creation result'}
            </Button>
          </div>
          {error ? (
            <ActionError
              error={error}
              title="Could not check the result"
              record="problem"
            />
          ) : null}
        </div>
      )
    }
    if (
      operation.data.state === 'failed' ||
      operation.data.state === 'cancelled'
    ) {
      return (
        <div className="grid justify-items-start gap-3">
          <p role="status" className="text-sm text-muted-foreground">
            {operation.data.state === 'cancelled'
              ? 'This approval is no longer valid.'
              : 'GitHub rejected the create request.'}
          </p>
          <Button
            variant="outline"
            className={touchTarget}
            onClick={() => {
              setOperationId('')
              setEditing(false)
              setError(null)
            }}
          >
            Prepare a new preview
          </Button>
        </div>
      )
    }
    return (
      <p role="status" className="text-sm text-muted-foreground">
        {operation.data.state === 'queued'
          ? 'Issue creation is queued.'
          : 'Issue creation is in progress.'}
      </p>
    )
  }

  if (operationId && operation.isPending) {
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Loading issue creation status…
      </p>
    )
  }
  if (operationId && operation.isError) {
    return (
      <div className="grid justify-items-start gap-3">
        <p role="alert" className="text-sm text-destructive">
          Could not load the saved issue creation status.
        </p>
        <Button
          variant="outline"
          className={touchTarget}
          onClick={() => void operation.refetch()}
        >
          Retry status check
        </Button>
      </div>
    )
  }

  if (!editing) {
    return (
      <div className="grid justify-items-start gap-3">
        <p className="text-sm text-muted-foreground">
          Create an issue in the repository selected in workspace settings.
        </p>
        <Button
          className={touchTarget}
          disabled={busy}
          onClick={() => void begin()}
        >
          {busy ? 'Loading preview…' : 'Create GitHub issue'}
        </Button>
        {error ? (
          <>
            <ActionError
              error={error}
              title="Could not prepare an issue"
              record="problem"
            />
            {error.reason === 'connection_not_ready' ? (
              <ConnectionGuidance />
            ) : null}
          </>
        ) : null}
      </div>
    )
  }

  return (
    <form className="grid gap-4" onSubmit={showPreview}>
      <div>
        <h3 className="font-medium">Review before publishing</h3>
        <p className="text-sm text-muted-foreground">
          Check the text for private details before it is sent to GitHub.
        </p>
      </div>
      {draft?.repository ? (
        <p className="text-sm">
          Destination: <span className="font-medium">{draft.repository}</span>
          {draft.visibility ? ` · ${draft.visibility}` : ''}
        </p>
      ) : null}
      <Field
        id={`${id}-title`}
        label="Issue title"
        required
        maxLength={256}
        value={title}
        disabled={busy}
        onChange={(event) => {
          setTitle(event.target.value)
          setPreviewed(false)
        }}
      />
      <TextareaField
        id={`${id}-body`}
        label="Issue body"
        maxLength={10000}
        rows={8}
        value={body}
        disabled={busy}
        onChange={(event) => {
          setBody(event.target.value)
          setPreviewed(false)
        }}
      />
      {previewed ? (
        <div className="grid gap-2 rounded-card border border-border bg-muted/30 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Exact preview
          </p>
          <h4 className="font-medium break-words">{title}</h4>
          <p className="whitespace-pre-wrap break-words text-sm">{body}</p>
          <p className="border-t border-border pt-2 font-mono text-xs text-muted-foreground">
            {draft?.body.match(/<!-- rescribo-operation:[^>]+ -->/)?.[0]}
          </p>
        </div>
      ) : null}
      {error ? (
        <>
          <ActionError
            error={error}
            title="The issue was not created"
            record="problem"
          />
          {error.reason === 'issue_creation_uncertain' ? (
            <Alert>
              <AlertTitle>GitHub may have created the issue</AlertTitle>
              <AlertDescription>
                Check GitHub before trying again. This request may have reached
                GitHub.
              </AlertDescription>
            </Alert>
          ) : null}
        </>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {!previewed ? (
          <Button
            type="submit"
            className={touchTarget}
            disabled={busy || !title.trim()}
          >
            Preview issue
          </Button>
        ) : (
          <Button
            type="button"
            className={touchTarget}
            disabled={busy || !draft}
            onClick={() => void publish()}
          >
            {busy ? 'Publishing…' : 'Publish issue'}
          </Button>
        )}
        <Button
          type="button"
          variant="outline"
          className={touchTarget}
          disabled={busy}
          onClick={() => setEditing(false)}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}

function ConnectionGuidance() {
  return (
    <div className="grid gap-1 rounded-card border border-border p-3 text-sm">
      <p>GitHub is not connected to this workspace.</p>
      <p className="text-muted-foreground">
        Ask a workspace owner to connect the selected repository.
      </p>
      <Link
        className="w-fit text-primary underline underline-offset-4"
        to="/settings"
      >
        Open workspace settings
      </Link>
    </div>
  )
}
