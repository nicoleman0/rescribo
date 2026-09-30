import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import {
  keepPreviousData,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import {
  assignProblemOwner,
  confirmProblemFix,
  editProblem,
  getProblem,
  listProblemReports,
  problemKeys,
  type ProblemDetail,
} from '@/api/problems'
import { confirmFixApplies, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'
import { useWorkspace } from '@/components/auth/use-workspace'
import { fieldError } from '@/components/forms/field-error'
import { Field, SelectField, TextareaField } from '@/components/forms/field'
import { touchTarget } from '@/components/layout/touch-target'
import { ActionError } from '@/components/states/action-error'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Provenance } from '@/features/inbox/provenance'
import { AssignReportForm } from '@/features/inbox/report-actions'
import { memberName } from '@/features/inbox/report-format'
import { TriageBadge } from '@/features/inbox/triage-badge'
import { useMembers } from '@/features/inbox/use-members'
import { cn } from '@/lib/utils'
import { PageNav } from './page-nav'
import { reportCountLabel } from './problem-format'
import { ProblemActivityList } from './problem-activity'
import { NeedsReviewBadge, ProblemStateBadge } from './problem-state'
import { GitHubIssueSection } from './github-issue-section'
import { useProblemMutation } from './use-problem-mutation'

const PROBLEM_REFRESH_MS = 30_000

export function ProblemDetailPage() {
  const { workspace } = useWorkspace()
  const { problemId = '' } = useParams()
  const client = useQueryClient()
  const problem = useQuery({
    queryKey: problemKeys.detail(workspace.id, problemId),
    queryFn: () => getProblem(workspace.id, problemId),
    retry: (failures, error) =>
      (error as ApiError).status !== 404 && failures < 2,
    refetchInterval: (query) => {
      const issueStatus = query.state.data?.engineering_issue?.refresh_status
      const createStatus = query.state.data?.current_create_operation?.state
      return issueStatus === 'pending' ||
        issueStatus === 'running' ||
        createStatus === 'queued' ||
        createStatus === 'running'
        ? 2_000
        : PROBLEM_REFRESH_MS
    },
    refetchIntervalInBackground: false,
  })
  useEffect(
    () => () => {
      void client.cancelQueries({
        queryKey: problemKeys.detail(workspace.id, problemId),
      })
    },
    [client, problemId, workspace.id],
  )
  return (
    <div className="grid max-w-4xl gap-6">
      <Button
        asChild
        variant="ghost"
        size="sm"
        className={cn('w-fit', touchTarget)}
      >
        <Link to="/problems">
          <ArrowLeft aria-hidden="true" />
          Back to problems
        </Link>
      </Button>
      {problem.isPending ? <LoadingState label="Loading problem" /> : null}
      {problem.isError && (problem.error as ApiError).status === 404 ? (
        <EmptyState
          title="Problem not found"
          description="It may belong to another workspace, or the link is wrong."
        />
      ) : null}
      {problem.isError && (problem.error as ApiError).status !== 404 ? (
        <ErrorState
          title="Could not load this problem"
          onRetry={() => void problem.refetch()}
          isRetrying={problem.isFetching}
        />
      ) : null}
      {problem.isSuccess ? (
        <ProblemBody workspaceId={workspace.id} problem={problem.data} />
      ) : null}
    </div>
  )
}

function ConfirmFixForm({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const id = useId()
  const [draft, setDraft] = useState({
    fix_note: '',
    fix_version: '',
    evidence_url: '',
  })
  const mutation = useProblemMutation(workspaceId, (input: typeof draft) =>
    confirmProblemFix(workspaceId, problem.id, {
      expected_version: problem.version,
      ...input,
    }),
  )
  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(draft)
  }
  return (
    <form
      aria-label="Confirm fix"
      className="grid max-w-lg gap-3 rounded-card border border-border p-4"
      onSubmit={submit}
      noValidate
    >
      <h2 className="font-semibold">Review and confirm fix</h2>
      <p className="text-sm text-muted-foreground">
        Confirm only after verifying that this fix is available to affected
        customers. This does not contact customers.
      </p>
      <fieldset disabled={mutation.isPending} className="grid gap-3">
        <TextareaField
          id={`${id}-note`}
          label="Fix details"
          required
          maxLength={10000}
          rows={3}
          value={draft.fix_note}
          error={fieldError(mutation.error, 'fix_note')}
          onChange={(event) =>
            setDraft({ ...draft, fix_note: event.target.value })
          }
        />
        <Field
          id={`${id}-version`}
          label="Available in version"
          required
          maxLength={100}
          value={draft.fix_version}
          error={fieldError(mutation.error, 'fix_version')}
          onChange={(event) =>
            setDraft({ ...draft, fix_version: event.target.value })
          }
        />
        <Field
          id={`${id}-evidence`}
          label="Evidence URL"
          type="url"
          maxLength={500}
          value={draft.evidence_url}
          error={fieldError(mutation.error, 'evidence_url')}
          onChange={(event) =>
            setDraft({ ...draft, evidence_url: event.target.value })
          }
        />
      </fieldset>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The fix was not confirmed"
          record="problem"
        />
      ) : null}
      <Button
        type="submit"
        className={cn('w-fit', touchTarget)}
        disabled={
          mutation.isPending ||
          !draft.fix_note.trim() ||
          !draft.fix_version.trim()
        }
      >
        {mutation.isPending ? 'Confirming…' : 'Confirm fix'}
      </Button>
    </form>
  )
}

function ProblemBody({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  return (
    <article className="grid gap-6">
      <ProblemHeader workspaceId={workspaceId} problem={problem} />
      {problem.state === 'open' || problem.state === 'in_progress' ? (
        <ConfirmFixForm workspaceId={workspaceId} problem={problem} />
      ) : problem.state === 'fix_available' ? (
        <section
          aria-label="Confirmed fix"
          className="grid gap-2 rounded-card border border-border p-4"
        >
          <h2 className="font-semibold">Confirmed fix</h2>
          <p className="text-sm">{problem.fix_note}</p>
          <p className="text-sm text-muted-foreground">
            Available in {problem.fix_version}
          </p>
          {problem.fix_evidence_url ? (
            <a
              className="text-sm underline"
              href={problem.fix_evidence_url}
              target="_blank"
              rel="noreferrer"
            >
              Fix evidence
            </a>
          ) : null}
        </section>
      ) : null}
      <OwnerForm workspaceId={workspaceId} problem={problem} />
      <Separator />
      <GitHubIssueSection workspaceId={workspaceId} problem={problem} />
      <Separator />
      <LinkedReports workspaceId={workspaceId} problem={problem} />
      <Separator />
      <ProblemActivityList workspaceId={workspaceId} problemId={problem.id} />
    </article>
  )
}

function ProblemHeader({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const [editing, setEditing] = useState(false)
  const editButton = useRef<HTMLButtonElement>(null)

  function stopEditing() {
    setEditing(false)
    requestAnimationFrame(() => editButton.current?.focus())
  }

  return (
    <header className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ProblemStateBadge state={problem.state} />
        {problem.needs_review ? <NeedsReviewBadge /> : null}
        <span className="font-mono text-[11px] text-muted-foreground">
          {reportCountLabel(problem.report_count)} · v{problem.version}
        </span>
      </div>
      {editing ? (
        <EditProblemForm
          workspaceId={workspaceId}
          problem={problem}
          onClose={stopEditing}
        />
      ) : (
        <>
          <h1 className="text-xl font-semibold break-words">{problem.title}</h1>
          {problem.summary ? (
            <p className="text-sm whitespace-pre-wrap">{problem.summary}</p>
          ) : (
            <p className="text-sm text-muted-foreground">No summary yet.</p>
          )}
          <Button
            ref={editButton}
            variant="outline"
            className={cn('w-fit', touchTarget)}
            onClick={() => setEditing(true)}
          >
            Edit title and summary
          </Button>
        </>
      )}
    </header>
  )
}

function EditProblemForm({
  workspaceId,
  problem,
  onClose,
}: {
  workspaceId: string
  problem: ProblemDetail
  onClose: () => void
}) {
  const id = useId()
  const [draft, setDraft] = useState({
    title: problem.title,
    summary: problem.summary,
  })
  // Only fields the member edited are sent. After a conflict, the other
  // member's value stays in any field this member did not touch.
  const [edited, setEdited] = useState<Set<keyof typeof draft>>(new Set())
  const changes = Object.fromEntries(
    [...edited]
      .filter((field) => draft[field] !== problem[field])
      .map((field) => [field, draft[field]]),
  )
  const mutation = useProblemMutation(
    workspaceId,
    (input: typeof changes) =>
      editProblem(workspaceId, problem.id, {
        expected_version: problem.version,
        ...input,
      }),
    onClose,
  )
  const unchanged = Object.keys(changes).length === 0

  function change(field: keyof typeof draft, value: string) {
    setDraft({ ...draft, [field]: value })
    setEdited(new Set(edited).add(field))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(changes)
  }

  return (
    <form
      aria-label="Edit problem"
      className="grid gap-3"
      onSubmit={submit}
      noValidate
    >
      <h1 className="sr-only">{problem.title}</h1>
      <fieldset disabled={mutation.isPending} className="grid gap-3">
        <Field
          id={`${id}-title`}
          label="Title"
          required
          maxLength={200}
          autoComplete="off"
          value={draft.title}
          error={fieldError(mutation.error, 'title')}
          onChange={(event) => change('title', event.target.value)}
        />
        <TextareaField
          id={`${id}-summary`}
          label="Summary"
          maxLength={10000}
          rows={4}
          value={draft.summary}
          error={fieldError(mutation.error, 'summary')}
          onChange={(event) => change('summary', event.target.value)}
        />
      </fieldset>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The problem was not saved"
          record="problem"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          className={touchTarget}
          disabled={mutation.isPending || unchanged}
        >
          {mutation.isPending ? 'Saving…' : 'Save changes'}
        </Button>
        <Button
          type="button"
          variant="outline"
          className={touchTarget}
          disabled={mutation.isPending}
          onClick={onClose}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}

function OwnerForm({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const id = useId()
  const members = useMembers(workspaceId)
  const saved = problem.owner?.id ?? ''
  // Follow the server value until the member picks one; keep their pick
  // through failures and conflicts.
  const [choice, setChoice] = useState<string | null>(null)
  const owner = choice ?? saved
  const mutation = useProblemMutation(
    workspaceId,
    (ownerId: string) =>
      assignProblemOwner(workspaceId, problem.id, {
        expected_version: problem.version,
        owner_id: ownerId || null,
      }),
    () => setChoice(null),
  )
  const current = problem.owner
  const currentIsListed =
    !current || members.data?.some((member) => member.id === current.id)

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(owner)
  }

  return (
    <form className="grid max-w-lg gap-2" onSubmit={submit} noValidate>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <SelectField
            id={`${id}-owner`}
            label="Owner"
            value={owner}
            disabled={mutation.isPending}
            error={fieldError(mutation.error, 'owner_id')}
            onChange={(event) => setChoice(event.target.value)}
          >
            <option value="">No owner</option>
            {members.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {memberName(member)}
              </option>
            ))}
            {currentIsListed ? null : (
              <option value={current.id}>{memberName(current)}</option>
            )}
          </SelectField>
        </div>
        <Button
          type="submit"
          variant="outline"
          className={cn('h-9', touchTarget)}
          disabled={mutation.isPending || owner === saved}
        >
          {mutation.isPending ? 'Saving…' : 'Save owner'}
        </Button>
      </div>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The owner was not changed"
          record="problem"
        />
      ) : null}
    </form>
  )
}

function LinkedReports({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const [page, setPage] = useState(1)
  const reports = useQuery({
    queryKey: problemKeys.reports(workspaceId, problem.id, page),
    queryFn: () => listProblemReports(workspaceId, problem.id, page),
    placeholderData: keepPreviousData,
  })
  return (
    <section aria-labelledby="linked-reports" className="grid gap-3">
      <h2 id="linked-reports" className="text-base font-semibold">
        Linked reports
      </h2>
      {reports.isPending ? <LoadingState label="Loading reports" /> : null}
      {reports.isError ? (
        <ErrorState
          title="Could not load the linked reports"
          onRetry={() => (page > 1 ? setPage(1) : void reports.refetch())}
          isRetrying={reports.isFetching}
        />
      ) : null}
      {reports.isSuccess && reports.data.count === 0 ? (
        <p className="text-sm text-muted-foreground">
          No reports are linked. The problem and its history are kept. Link a
          report from the Inbox.
        </p>
      ) : null}
      {reports.isSuccess && reports.data.count > 0 ? (
        <div
          aria-busy={reports.isPlaceholderData}
          className={cn(
            'grid gap-3',
            reports.isPlaceholderData && 'opacity-60',
          )}
        >
          <ul aria-label="Linked reports" className="grid gap-3">
            {reports.data.results.map((report) => (
              <li
                key={report.id}
                className="grid gap-3 rounded-card border border-border bg-card p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <Link
                    to={`/inbox/${report.id}`}
                    className="min-w-0 font-medium break-words text-primary underline-offset-4 hover:underline"
                  >
                    {report.title}
                  </Link>
                  <TriageBadge state={report.triage_state} />
                </div>
                <p className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span>{report.customer_label || 'No customer'}</span>
                  <span>Submitted by {memberName(report.submitted_by)}</span>
                </p>
                <Provenance
                  provenance={report.provenance}
                  submittedBy={report.submitted_by}
                />
                <AssignReportForm workspaceId={workspaceId} report={report} />
                {problem.state === 'fix_available' &&
                report.follow_up_revision !== problem.resolution_revision ? (
                  <ConfirmFixAppliesButton
                    workspaceId={workspaceId}
                    report={report}
                    onConfirmed={() => reports.refetch()}
                  />
                ) : null}
              </li>
            ))}
          </ul>
          <PageNav
            label="Linked report pages"
            count={reportCountLabel(reports.data.count)}
            page={reports.data}
            pageNumber={page}
            onPage={(next) => setPage(next ?? 1)}
          />
        </div>
      ) : null}
    </section>
  )
}

function ConfirmFixAppliesButton({
  workspaceId,
  report,
  onConfirmed,
}: {
  workspaceId: string
  report: ReportDetail
  onConfirmed: () => void
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  async function confirm() {
    setPending(true)
    setError(null)
    try {
      await confirmFixApplies(workspaceId, report.id, {
        expected_version: report.version,
      })
      onConfirmed()
    } catch (caught) {
      setError(caught as ApiError)
    } finally {
      setPending(false)
    }
  }
  return (
    <div className="grid justify-items-start gap-2">
      <p className="text-sm">
        Verify this existing fix applies to this report.
      </p>
      <Button
        type="button"
        variant="outline"
        className={touchTarget}
        disabled={pending}
        onClick={() => void confirm()}
      >
        {pending ? 'Recording…' : 'Confirm fix applies'}
      </Button>
      {error ? (
        <ActionError
          error={error}
          title="The follow-up was not created"
          record="report"
        />
      ) : null}
    </div>
  )
}
