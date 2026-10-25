import { useId, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  changeProblemState,
  type ProblemDetail,
  type ProblemState,
} from '@/api/problems'
import { ConfirmPanel } from '@/components/confirm/confirm-panel'
import { fieldError } from '@/components/forms/field-error'
import { TextareaField } from '@/components/forms/field'
import { ActionError } from '@/components/states/action-error'
import { Button } from '@/components/ui/button'
import { problemStateLabels } from './problem-format'
import { problemCard, problemCardHeading } from './problem-card'
import { ProblemStateBadge } from './problem-state'
import { useProblemMutation } from './use-problem-mutation'

type StateAction = 'start' | 'stop' | 'decline' | 'reopen'

export function DeclineProblemForm({
  workspaceId,
  problem,
  onCancel,
  onSuccess,
}: {
  workspaceId: string
  problem: ProblemDetail
  onCancel: () => void
  onSuccess?: () => void
}) {
  const id = useId()
  const [reason, setReason] = useState('')
  const mutation = useProblemMutation(
    workspaceId,
    (input: { reason: string }) =>
      changeProblemState(workspaceId, problem.id, {
        expected_version: problem.version,
        action: 'decline',
        reason: input.reason,
      }),
    () => {
      toast.success('Status changed to Not planned')
      onSuccess?.()
    },
  )
  return (
    <ConfirmPanel
      title="Mark not planned"
      description="Give a reason so the team knows why no fix is planned."
      confirmLabel="Mark not planned"
      pendingLabel="Saving…"
      isPending={mutation.isPending}
      confirmDisabled={!reason.trim()}
      onConfirm={() => mutation.mutate({ reason })}
      onCancel={onCancel}
    >
      <TextareaField
        id={`${id}-reason`}
        label="Reason"
        maxLength={2000}
        required
        value={reason}
        error={fieldError(mutation.error, 'reason')}
        onChange={(event) => setReason(event.target.value)}
      />
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The problem was not changed"
          record="problem"
        />
      ) : null}
    </ConfirmPanel>
  )
}

function runStateAction(
  action: StateAction,
  problem: ProblemDetail,
  workspaceId: string,
) {
  return changeProblemState(workspaceId, problem.id, {
    expected_version: problem.version,
    action,
  })
}

export function ProblemStatusCard({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const [declining, setDeclining] = useState(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const onSuccess = (saved: ProblemDetail) => {
    toast.success(`Status changed to ${problemStateLabels[saved.state]}`)
    requestAnimationFrame(() => heading.current?.focus())
  }
  const start = useProblemMutation<void>(
    workspaceId,
    () => runStateAction('start', problem, workspaceId),
    onSuccess,
  )
  const stop = useProblemMutation<void>(
    workspaceId,
    () => runStateAction('stop', problem, workspaceId),
    onSuccess,
  )
  const reopen = useProblemMutation<void>(
    workspaceId,
    () => runStateAction('reopen', problem, workspaceId),
    onSuccess,
  )
  if (problem.state === 'fix_available') return null
  const actions: Partial<
    Record<ProblemState, { label: string; run: () => void; pending: boolean }>
  > = {
    open: {
      label: 'Start work',
      run: () => start.mutate(undefined),
      pending: start.isPending,
    },
    in_progress: {
      label: 'Move back to open',
      run: () => stop.mutate(undefined),
      pending: stop.isPending,
    },
    not_planned: {
      label: 'Reopen',
      run: () => reopen.mutate(undefined),
      pending: reopen.isPending,
    },
  }
  const currentAction = actions[problem.state]
  const error = start.error ?? stop.error ?? reopen.error

  return (
    <section className={problemCard} aria-labelledby="problem-status-heading">
      <h2
        id="problem-status-heading"
        ref={heading}
        className={problemCardHeading}
        tabIndex={-1}
      >
        Status
      </h2>
      <ProblemStateBadge state={problem.state} />
      {problem.state === 'not_planned' ? (
        <p className="break-words whitespace-pre-wrap">
          {problem.not_planned_reason}
        </p>
      ) : null}
      {declining ? (
        <DeclineProblemForm
          workspaceId={workspaceId}
          problem={problem}
          onCancel={() => setDeclining(false)}
          onSuccess={() => {
            setDeclining(false)
            requestAnimationFrame(() => heading.current?.focus())
          }}
        />
      ) : currentAction ? (
        <div className="flex flex-wrap gap-2">
          <Button disabled={currentAction.pending} onClick={currentAction.run}>
            {currentAction.pending ? 'Saving…' : currentAction.label}
          </Button>
          {problem.state !== 'not_planned' ? (
            <Button variant="outline" onClick={() => setDeclining(true)}>
              Mark not planned
            </Button>
          ) : null}
        </div>
      ) : null}
      {error ? (
        <ActionError
          error={error}
          title="The status was not changed"
          record="problem"
        />
      ) : null}
    </section>
  )
}
