import { useId, useRef, useState, type FormEvent, type RefObject } from 'react'
import type { ProblemListItem } from '@/api/problems'
import {
  assignReport,
  createProblemForReport,
  linkReport,
  transitionReport,
  type ReportDetail,
} from '@/api/reports'
import { fieldError } from '@/components/forms/field-error'
import { Field, SelectField, TextareaField } from '@/components/forms/field'
import { ActionError } from '@/components/states/action-error'
import { ErrorState } from '@/components/states/async-states'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ProblemPicker } from '@/features/problems/problem-picker'

import { memberName } from './report-format'
import { useMembers } from './use-members'
import { useReportMutation } from './use-report-mutation'

type Panel = 'link' | 'create' | null

/** Triage controls for one report: assignment, grouping, and dismissal. */
export function ReportTriage({
  workspaceId,
  report,
}: {
  workspaceId: string
  report: ReportDetail
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  return (
    <section aria-labelledby={`triage-${report.id}`} className="grid gap-4">
      <h3
        id={`triage-${report.id}`}
        ref={heading}
        tabIndex={-1}
        className="font-medium outline-none"
      >
        Triage
      </h3>
      {report.problem?.state === 'fix_available' ? (
        <Alert>
          <AlertTitle>Check that the fix applies</AlertTitle>
          <AlertDescription>
            This problem already has a confirmed fix. Linking the report did not
            confirm that the fix applies or send a message. Review applicability
            on the linked problem.
            {report.problem ? (
              <>
                {' '}
                <a
                  className="underline"
                  href={`/problems/${report.problem.id}`}
                >
                  Review fix applicability
                </a>
                .
              </>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}
      {/* Grouping is the usual next step, so it comes before assignment. */}
      <GroupingActions
        workspaceId={workspaceId}
        report={report}
        onDone={() => heading.current?.focus()}
      />
      <AssignReportForm workspaceId={workspaceId} report={report} />
    </section>
  )
}

/** Assign or clear the member responsible for a report. */
export function AssignReportForm({
  workspaceId,
  report,
}: {
  workspaceId: string
  report: ReportDetail
}) {
  const id = useId()
  const members = useMembers(workspaceId)
  const saved = report.assignee?.id ?? ''
  // Follow the server value until the member picks one; keep their pick
  // through failures and conflicts.
  const [choice, setChoice] = useState<string | null>(null)
  const assignee = choice ?? saved
  const mutation = useReportMutation(
    workspaceId,
    (assigneeId: string) =>
      assignReport(workspaceId, report.id, {
        expected_version: report.version,
        assignee_id: assigneeId || null,
      }),
    () => setChoice(null),
  )
  const current = report.assignee
  const currentIsListed =
    !current || members.data?.some((member) => member.id === current.id)

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(assignee)
  }

  return (
    <form className="grid gap-2" onSubmit={submit} noValidate>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <SelectField
            id={`${id}-assignee`}
            label="Assignee"
            value={assignee}
            disabled={mutation.isPending}
            error={fieldError(mutation.error, 'assignee_id')}
            onChange={(event) => setChoice(event.target.value)}
          >
            <option value="">Unassigned</option>
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
          className="h-9"
          disabled={mutation.isPending || assignee === saved}
        >
          {mutation.isPending ? 'Saving…' : 'Save assignee'}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        A new assignee cancels any unsent employee notification prepared for
        this report. It does not notify anyone or record customer contact.
      </p>
      {members.isError ? (
        <ErrorState
          title="Could not load members"
          description="Retry to update the assignee choices."
          onRetry={() => void members.refetch()}
          isRetrying={members.isFetching}
        />
      ) : null}
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The assignee was not changed"
          record="report"
        />
      ) : null}
    </form>
  )
}

function GroupingActions({
  workspaceId,
  report,
  onDone,
}: {
  workspaceId: string
  report: ReportDetail
  onDone: () => void
}) {
  const [panel, setPanel] = useState<Panel>(null)
  const linkButton = useRef<HTMLButtonElement>(null)
  const createButton = useRef<HTMLButtonElement>(null)
  const transition = useReportMutation(
    workspaceId,
    (action: 'unlink' | 'dismiss' | 'restore') =>
      transitionReport(workspaceId, report.id, action, {
        expected_version: report.version,
      }),
    onDone,
  )
  const linked = report.triage_state === 'linked'

  function close(opener: RefObject<HTMLButtonElement | null>) {
    setPanel(null)
    // The opener re-renders once the panel closes; focus it on the next frame.
    requestAnimationFrame(() => opener.current?.focus())
  }

  function finish() {
    setPanel(null)
    onDone()
  }

  if (report.triage_state === 'dismissed') {
    return (
      <div className="grid gap-2">
        <p className="text-sm text-muted-foreground">
          Dismissed reports are kept but not grouped or followed up.
        </p>
        <Button
          variant="outline"
          className="w-fit"
          disabled={transition.isPending}
          onClick={() => transition.mutate('restore')}
        >
          {transition.isPending ? 'Restoring…' : 'Restore report'}
        </Button>
        {transition.isError ? (
          <ActionError
            error={transition.error}
            title="The report was not restored"
            record="report"
          />
        ) : null}
      </div>
    )
  }

  return (
    <div className="grid gap-3">
      {panel === null ? (
        <div className="flex flex-wrap gap-2">
          <Button
            ref={linkButton}
            variant="outline"
            disabled={transition.isPending}
            onClick={() => setPanel('link')}
          >
            {linked ? 'Move to problem' : 'Link to problem'}
          </Button>
          <Button
            ref={createButton}
            variant="outline"
            disabled={transition.isPending}
            onClick={() => setPanel('create')}
          >
            {linked ? 'Move to new problem' : 'Create problem'}
          </Button>
          <Button
            variant={linked ? 'outline' : 'destructive'}
            disabled={transition.isPending}
            onClick={() => transition.mutate(linked ? 'unlink' : 'dismiss')}
          >
            {transition.isPending ? 'Saving…' : linked ? 'Ungroup' : 'Dismiss'}
          </Button>
        </div>
      ) : null}
      {linked && panel === null ? (
        <p className="text-xs text-muted-foreground">
          Ungrouping returns the report to New. Moving or ungrouping cancels any
          unsent employee notification; sent history is kept.
        </p>
      ) : null}
      {transition.isError ? (
        <ActionError
          error={transition.error}
          title="The report was not updated"
          record="report"
        />
      ) : null}
      {panel === 'link' ? (
        <LinkPanel
          workspaceId={workspaceId}
          report={report}
          onCancel={() => close(linkButton)}
          onDone={finish}
        />
      ) : null}
      {panel === 'create' ? (
        <CreateProblemPanel
          workspaceId={workspaceId}
          report={report}
          onCancel={() => close(createButton)}
          onDone={finish}
        />
      ) : null}
    </div>
  )
}

function LinkPanel({
  workspaceId,
  report,
  onCancel,
  onDone,
}: {
  workspaceId: string
  report: ReportDetail
  onCancel: () => void
  onDone: () => void
}) {
  const [choice, setChoice] = useState<ProblemListItem | null>(null)
  const mutation = useReportMutation(
    workspaceId,
    (problemId: string) =>
      linkReport(workspaceId, report.id, {
        expected_version: report.version,
        problem_id: problemId,
      }),
    onDone,
  )
  const verb = report.problem ? 'Move' : 'Link'

  function submit(event: FormEvent) {
    event.preventDefault()
    if (choice) mutation.mutate(choice.id)
  }

  return (
    <form
      aria-label={`${verb} to an existing problem`}
      className="grid gap-3 rounded-card border border-border p-3"
      onSubmit={submit}
      noValidate
    >
      <ProblemPicker
        workspaceId={workspaceId}
        excludeId={report.problem?.id}
        selectedId={choice?.id}
        onSelect={setChoice}
        disabled={mutation.isPending}
      />
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The report was not linked"
          record="report"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!choice || mutation.isPending}>
          {mutation.isPending ? 'Saving…' : `${verb} report`}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={mutation.isPending}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}

function CreateProblemPanel({
  workspaceId,
  report,
  onCancel,
  onDone,
}: {
  workspaceId: string
  report: ReportDetail
  onCancel: () => void
  onDone: () => void
}) {
  const id = useId()
  const members = useMembers(workspaceId)
  // Start from the report title only. Customer details and captured text
  // stay on the report unless a member copies them deliberately.
  const [draft, setDraft] = useState({
    title: report.title,
    summary: '',
    owner: '',
  })
  const mutation = useReportMutation(
    workspaceId,
    (input: typeof draft) =>
      createProblemForReport(workspaceId, report.id, {
        expected_version: report.version,
        title: input.title,
        summary: input.summary,
        owner_id: input.owner || null,
      }),
    onDone,
  )
  const verb = report.problem ? 'move' : 'link'

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(draft)
  }

  return (
    <form
      aria-label="Create a problem for this report"
      className="grid gap-3 rounded-card border border-border p-3"
      onSubmit={submit}
      noValidate
    >
      <fieldset disabled={mutation.isPending} className="grid gap-3">
        <Field
          id={`${id}-title`}
          label="Problem title"
          required
          maxLength={200}
          autoComplete="off"
          value={draft.title}
          error={fieldError(mutation.error, 'title')}
          onChange={(event) =>
            setDraft({ ...draft, title: event.target.value })
          }
        />
        <TextareaField
          id={`${id}-summary`}
          label="Summary"
          hint="Optional. Describe the shared problem, not one customer."
          maxLength={10000}
          rows={3}
          value={draft.summary}
          error={fieldError(mutation.error, 'summary')}
          onChange={(event) =>
            setDraft({ ...draft, summary: event.target.value })
          }
        />
        <SelectField
          id={`${id}-owner`}
          label="Owner"
          value={draft.owner}
          error={fieldError(mutation.error, 'owner_id')}
          onChange={(event) =>
            setDraft({ ...draft, owner: event.target.value })
          }
        >
          <option value="">No owner</option>
          {members.data?.map((member) => (
            <option key={member.id} value={member.id}>
              {memberName(member)}
            </option>
          ))}
        </SelectField>
      </fieldset>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The problem was not created"
          record="report"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating…' : `Create and ${verb}`}
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={mutation.isPending}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
