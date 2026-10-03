import { useId, useState, type FormEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { linkGitHubIssue, refreshGitHubIssue } from '@/api/github-issues'
import { applyProblem } from '@/api/cache'
import { problemKeys, type ProblemDetail } from '@/api/problems'
import type { ApiError } from '@/api/request'
import { Field } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { touchTarget } from '@/components/layout/touch-target'
import { ActionError } from '@/components/states/action-error'
import { Button } from '@/components/ui/button'
import { GitHubIssueCreate } from './github-issue-create'
import { GitHubIssueStatus } from './github-issue-status'

export function GitHubIssueSection({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const id = useId()
  const client = useQueryClient()
  const issue = problem.engineering_issue
  const [reference, setReference] = useState('')
  const [replacing, setReplacing] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  async function link(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const updated = await linkGitHubIssue(workspaceId, problem.id, {
        expected_version: problem.version,
        reference,
        replace: replacing,
      })
      applyProblem(client, workspaceId, updated)
      setReference('')
      setReplacing(false)
    } catch (cause) {
      const apiError = cause as ApiError
      if (apiError.current)
        applyProblem(client, workspaceId, apiError.current as ProblemDetail)
      setError(apiError)
    } finally {
      setBusy(false)
    }
  }

  async function refresh() {
    setBusy(true)
    setError(null)
    try {
      await refreshGitHubIssue(workspaceId, problem.id, {
        issue_id: issue?.id ?? '',
      })
      void client.invalidateQueries({
        queryKey: problemKeys.detail(workspaceId, problem.id),
      })
    } catch (cause) {
      setError(cause as ApiError)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby={`${id}-heading`} className="grid gap-4">
      <div>
        <h2 id={`${id}-heading`} className="text-lg font-semibold">
          GitHub issue
        </h2>
        <p className="text-sm text-muted-foreground">
          GitHub tracks the engineering work. A closed issue still needs a
          person to review the fix.
        </p>
      </div>
      {issue ? (
        <>
          <GitHubIssueStatus issue={issue} />
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              className={touchTarget}
              disabled={busy}
              onClick={() => void refresh()}
            >
              {busy ? 'Checking…' : 'Refresh status'}
            </Button>
            <Button
              variant="outline"
              className={touchTarget}
              disabled={busy}
              aria-expanded={replacing}
              onClick={() => {
                setReplacing(!replacing)
                setError(null)
              }}
            >
              {replacing ? 'Keep current link' : 'Replace link'}
            </Button>
          </div>
          {replacing ? (
            <LinkIssueForm
              id={id}
              reference={reference}
              setReference={setReference}
              onSubmit={link}
              busy={busy}
              replacing
              error={error}
            />
          ) : null}
        </>
      ) : (
        <>
          <LinkIssueForm
            id={id}
            reference={reference}
            setReference={setReference}
            onSubmit={link}
            busy={busy}
            error={error}
          />
          <GitHubIssueCreate workspaceId={workspaceId} problem={problem} />
        </>
      )}
      {error && issue && !replacing ? (
        <ActionError
          error={error}
          title="GitHub did not update the issue"
          record="problem"
        />
      ) : null}
    </section>
  )
}

function LinkIssueForm({
  id,
  reference,
  setReference,
  onSubmit,
  busy,
  replacing = false,
  error,
}: {
  id: string
  reference: string
  setReference: (value: string) => void
  onSubmit: (event: FormEvent) => void
  busy: boolean
  replacing?: boolean
  error: ApiError | null
}) {
  return (
    <form className="grid max-w-xl gap-3" onSubmit={onSubmit}>
      <Field
        id={`${id}-reference`}
        label={
          replacing ? 'Replacement issue URL or number' : 'Issue URL or number'
        }
        placeholder="https://github.com/org/repo/issues/123"
        autoComplete="url"
        value={reference}
        disabled={busy}
        error={fieldError(error, 'reference')}
        onChange={(event) => setReference(event.target.value)}
      />
      <p className="text-xs text-muted-foreground">
        The issue must belong to the repository selected in workspace settings.
        Pull requests cannot be linked.
      </p>
      {error ? (
        <ActionError
          error={error}
          title="The issue was not linked"
          record="problem"
        />
      ) : null}
      <Button
        type="submit"
        variant="outline"
        className={touchTarget}
        disabled={busy || !reference.trim()}
      >
        {busy
          ? 'Checking issue…'
          : replacing
            ? 'Replace linked issue'
            : 'Link existing issue'}
      </Button>
    </form>
  )
}
