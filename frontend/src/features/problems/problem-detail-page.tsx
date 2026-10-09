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
  unlinkFixRelease,
  type ProblemDetail,
} from '@/api/problems'
import { confirmFixApplies, type ReportDetail } from '@/api/reports'
import type { ApiError } from '@/api/request'
import { useReportMutation } from '@/features/inbox/use-report-mutation'
import {
  demoDescription,
  useIsDemo,
  useWorkspace,
} from '@/components/auth/use-workspace'
import { fieldError } from '@/components/forms/field-error'
import { Field, SelectField, TextareaField } from '@/components/forms/field'
import { touchTarget } from '@/components/layout/touch-target'
import { PageTitle } from '@/components/layout/page-title'
import { ActionError } from '@/components/states/action-error'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import {
  formatDate,
  memberName,
  sourceLabel,
} from '@/features/inbox/report-format'
import { TriageBadge } from '@/features/inbox/triage-badge'
import { useMembers } from '@/features/inbox/use-members'
import { cn } from '@/lib/utils'
import { PageNav } from './page-nav'
import { problemCard, problemCardHeading } from './problem-card'
import { reportCountLabel } from './problem-format'
import { ProblemActivityList } from './problem-activity'
import { ProblemNextStep } from './problem-next-step'
import { NeedsReviewBadge, ProblemStateBadge } from './problem-state'
import { GitHubIssueSection } from './github-issue-section'
import { ReportAssigneeEditor } from './report-assignee-editor'
import { ReleasePicker } from './release-picker'
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
      ![403, 404].includes((error as ApiError).status ?? 0) && failures < 2,
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
    <div className="animate-page-enter grid max-w-5xl gap-6">
      <PageTitle title={problem.data?.title ?? 'Problem'} />
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
      {problem.isError && (problem.error as ApiError).status === 403 ? (
        <EmptyState
          title="Problem access removed"
          description="You no longer have access to this problem."
        />
      ) : null}
      {problem.isError &&
      ![403, 404].includes((problem.error as ApiError).status ?? 0) &&
      !problem.data ? (
        <ErrorState
          title="Could not load this problem"
          onRetry={() => void problem.refetch()}
          isRetrying={problem.isFetching}
        />
      ) : null}
      {problem.isError &&
      problem.data &&
      ![403, 404].includes((problem.error as ApiError).status ?? 0) ? (
        <ErrorState
          title="Could not refresh this problem"
          description="Your open changes are still here. Retry to check for updates."
          onRetry={() => void problem.refetch()}
          isRetrying={problem.isFetching}
        />
      ) : null}
      {problem.data &&
      !(
        problem.isError &&
        [403, 404].includes((problem.error as ApiError).status ?? 0)
      ) ? (
        <ReadyState>
          <ProblemBody workspaceId={workspace.id} problem={problem.data} />
        </ReadyState>
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
      className={problemCard}
      onSubmit={submit}
      noValidate
    >
      <h2 className={problemCardHeading}>Fix</h2>
      <p className="text-muted-foreground">
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
      <ProblemNextStep workspaceId={workspaceId} problem={problem} />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        {/* First in the DOM so phones show the fix and owner before the
            report list; wide screens move it to the side column. */}
        <div className="grid min-w-0 gap-4 lg:col-start-2 lg:row-start-1">
          <FixCard workspaceId={workspaceId} problem={problem} />
          <GitHubIssueSection workspaceId={workspaceId} problem={problem} />
          <OwnerCard workspaceId={workspaceId} problem={problem} />
        </div>
        <div className="grid min-w-0 gap-8 lg:col-start-1 lg:row-start-1">
          <LinkedReports workspaceId={workspaceId} problem={problem} />
          <ProblemActivityList
            workspaceId={workspaceId}
            problemId={problem.id}
          />
        </div>
      </div>
    </article>
  )
}

export function FixCard({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const [choosingRelease, setChoosingRelease] = useState(false)
  const isDemo = useIsDemo()
  const unlink = useProblemMutation(workspaceId, () =>
    unlinkFixRelease(workspaceId, problem.id, {
      expected_version: problem.version,
    }),
  )
  if (problem.state === 'open' || problem.state === 'in_progress')
    return <ConfirmFixForm workspaceId={workspaceId} problem={problem} />
  if (problem.state !== 'fix_available') return null
  return (
    <section aria-label="Confirmed fix" className={problemCard}>
      <h2 className={problemCardHeading}>Confirmed fix</h2>
      <p className="break-words whitespace-pre-wrap">{problem.fix_note}</p>
      <p className="text-muted-foreground">
        Available in {problem.fix_version}
        {problem.fix_confirmed_by && problem.fix_confirmed_at ? (
          <>
            {'. Confirmed by '}
            {memberName(problem.fix_confirmed_by)} on{' '}
            <time dateTime={problem.fix_confirmed_at}>
              {formatDate(problem.fix_confirmed_at)}
            </time>
          </>
        ) : null}
      </p>
      {problem.fix_evidence_url ? (
        <a
          className="w-fit text-primary underline-offset-4 hover:underline"
          href={problem.fix_evidence_url}
          target="_blank"
          rel="noreferrer"
        >
          Fix evidence
          <span className="sr-only"> (opens in a new tab)</span>
        </a>
      ) : null}
      {problem.fix_release ? (
        <div className="grid gap-2">
          <a
            className="w-fit text-primary underline-offset-4 hover:underline"
            href={problem.fix_release.url}
            target="_blank"
            rel="noreferrer"
          >
            {problem.fix_release.tag_name}
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
          {problem.fix_release.name !== problem.fix_release.tag_name ? (
            <p>{problem.fix_release.name}</p>
          ) : null}
          <time
            className="text-muted-foreground"
            dateTime={problem.fix_release.published_at}
          >
            {formatDate(problem.fix_release.published_at)}
          </time>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          className={touchTarget}
          disabled={isDemo || unlink.isPending}
          onClick={() => setChoosingRelease(!choosingRelease)}
        >
          {problem.fix_release ? 'Change release' : 'Link a release'}
        </Button>
        {problem.fix_release ? (
          <Button
            variant="outline"
            className={touchTarget}
            disabled={isDemo || unlink.isPending}
            onClick={() => unlink.mutate(undefined)}
          >
            {unlink.isPending ? 'Removing…' : 'Remove release'}
          </Button>
        ) : null}
      </div>
      {unlink.error ? (
        <ActionError
          error={unlink.error}
          title="The release was not removed"
          record="problem"
        />
      ) : null}
      {isDemo ? (
        <p className="text-xs text-muted-foreground">{demoDescription}</p>
      ) : null}
      {choosingRelease ? (
        <ReleasePicker
          workspaceId={workspaceId}
          problem={problem}
          onCancel={() => setChoosingRelease(false)}
        />
      ) : null}
    </section>
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
            <p className="min-w-0 break-words text-sm whitespace-pre-wrap">
              {problem.summary}
            </p>
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

function OwnerCard({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const id = useId()
  const [editing, setEditing] = useState(false)
  return (
    <div className={problemCard}>
      <div className="flex items-center justify-between gap-2">
        <h2 className={problemCardHeading}>Owner</h2>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className={touchTarget}
          aria-expanded={editing}
          aria-controls={editing ? id : undefined}
          aria-label={editing ? 'Cancel changing the owner' : 'Change owner'}
          onClick={() => setEditing(!editing)}
        >
          {editing ? 'Cancel' : 'Change'}
        </Button>
      </div>
      {editing ? (
        <div id={id}>
          <OwnerForm
            workspaceId={workspaceId}
            problem={problem}
            onSaved={() => setEditing(false)}
          />
        </div>
      ) : (
        <p className={cn(!problem.owner && 'text-muted-foreground')}>
          {problem.owner ? memberName(problem.owner) : 'No owner'}
        </p>
      )}
    </div>
  )
}

function OwnerForm({
  workspaceId,
  problem,
  onSaved,
}: {
  workspaceId: string
  problem: ProblemDetail
  onSaved: () => void
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
    () => {
      setChoice(null)
      onSaved()
    },
  )
  const current = problem.owner
  const currentIsListed =
    !current || members.data?.some((member) => member.id === current.id)

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(owner)
  }

  return (
    <form className="grid gap-2" onSubmit={submit} noValidate>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-40 flex-1">
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
      <h2 id="linked-reports" className="text-sm font-semibold">
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
        <ReadyState
          aria-busy={reports.isPlaceholderData}
          className={cn(
            'grid gap-3',
            reports.isPlaceholderData && 'opacity-60',
          )}
        >
          <ul
            aria-label="Linked reports"
            className="divide-y divide-border rounded-card bg-card shadow-elevation-1"
          >
            {reports.data.results.map((report) => (
              <li
                key={report.id}
                className="grid gap-x-4 gap-y-1 px-4 py-3 md:grid-cols-[minmax(0,1fr)_minmax(0,12rem)] md:items-center"
              >
                <div className="grid min-w-0 gap-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <Link
                      to={`/inbox/${report.id}`}
                      className="min-w-0 font-medium break-words text-primary underline-offset-4 hover:underline"
                    >
                      {report.title}
                    </Link>
                    <TriageBadge state={report.triage_state} />
                  </div>
                  <p className="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
                    <span>{report.customer_label || 'No customer'}</span>
                    <span aria-hidden="true">·</span>
                    <span>{sourceLine(report)}</span>
                  </p>
                </div>
                <ReportAssigneeEditor
                  workspaceId={workspaceId}
                  report={report}
                />
                {problem.state === 'fix_available' &&
                report.follow_up_revision !== problem.resolution_revision ? (
                  <ConfirmFixAppliesButton
                    workspaceId={workspaceId}
                    report={report}
                    resolutionRevision={problem.resolution_revision}
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
        </ReadyState>
      ) : null}
    </section>
  )
}

/** One line on where a report came from. The captured message, its link,
 * and link retry stay on the report page. */
function sourceLine(report: ReportDetail) {
  const source = report.provenance
  if (source.kind === 'manual')
    return `Manual entry by ${memberName(report.submitted_by)}`
  const author = source.author_display_name
  return `${sourceLabel(source.kind)} message${author ? ` by ${author}` : ''}`
}

function ConfirmFixAppliesButton({
  workspaceId,
  report,
  resolutionRevision,
}: {
  workspaceId: string
  report: ReportDetail
  resolutionRevision: number
}) {
  const mutation = useReportMutation(workspaceId, () =>
    confirmFixApplies(workspaceId, report.id, {
      expected_version: report.version,
      expected_resolution_revision: resolutionRevision,
    }),
  )
  return (
    <div className="grid justify-items-start gap-2 pt-2 md:col-span-2">
      <p className="text-sm">
        Verify this existing fix applies to this report.
      </p>
      <Button
        type="button"
        variant="outline"
        className={touchTarget}
        disabled={mutation.isPending}
        onClick={() => mutation.mutate(undefined)}
      >
        {mutation.isPending ? 'Recording…' : 'Confirm fix applies'}
      </Button>
      {mutation.error ? (
        <ActionError
          error={mutation.error}
          title="The follow-up was not created"
          record="report"
        />
      ) : null}
    </div>
  )
}
