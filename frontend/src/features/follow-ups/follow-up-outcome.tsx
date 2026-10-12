import { useContext, useId, useState, type FormEvent } from 'react'
import {
  correctFollowUpOutcome,
  recordFollowUpOutcome,
  type FollowUpContactState,
  type FollowUpDetail,
} from '@/api/follow-ups'
import { Button } from '@/components/ui/button'
import { ActionError } from '@/components/states/action-error'
import { SelectField, TextareaField } from '@/components/forms/field'
import { formatDate, memberName } from '@/features/inbox/report-format'
import { cn } from '@/lib/utils'
import { contactStateLabels } from './follow-ups-format'
import { useFollowUpMutation } from './follow-ups-mutation'
import {
  FollowUpLayoutContext,
  useSectionClass,
  wrapLongText,
} from './follow-up-layout'
import { SectionHeading } from './follow-up-section-heading'

function choicesFor(state: FollowUpContactState) {
  const choices: { value: FollowUpContactState; label: string }[] = []
  if (state === 'pending') {
    choices.push(
      { value: 'contacted', label: 'Customer contacted' },
      { value: 'still_affected', label: 'Still affected' },
      { value: 'no_response', label: 'No response' },
    )
  } else if (state === 'contacted') {
    choices.push(
      { value: 'confirmed', label: 'Customer confirmed' },
      { value: 'still_affected', label: 'Still affected' },
      { value: 'no_response', label: 'No response' },
    )
  }
  return choices
}

export function ContactSection({
  workspaceId,
  followUp,
  isOwner,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  isOwner: boolean
}) {
  return (
    <section aria-label="Customer contact" className={useSectionClass()}>
      <SectionHeading>Customer contact</SectionHeading>
      <p className="text-sm text-muted-foreground">
        Outcome: {contactStateLabels[followUp.outcome.state]}.
      </p>
      {followUp.outcome.note ? (
        <p className={cn(wrapLongText, 'text-sm')}>
          <span className="text-muted-foreground">Note: </span>
          {followUp.outcome.note}
        </p>
      ) : null}
      {followUp.outcome.by ? (
        <p className="text-sm text-muted-foreground">
          Recorded by {memberName(followUp.outcome.by)}{' '}
          {followUp.outcome.at ? formatDate(followUp.outcome.at) : ''}
        </p>
      ) : null}
      <RecordOutcomeForm
        workspaceId={workspaceId}
        followUp={followUp}
        isOwner={isOwner}
      />
    </section>
  )
}

function RecordOutcomeForm({
  workspaceId,
  followUp,
  isOwner,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  isOwner: boolean
}) {
  const id = useId()
  const layout = useContext(FollowUpLayoutContext)
  const choices = choicesFor(followUp.outcome.state)
  const [choice, setChoice] = useState<FollowUpContactState | null>(null)
  const [note, setNote] = useState('')
  const record = useFollowUpMutation(
    workspaceId,
    ({
      state: nextState,
      note: nextNote,
    }: {
      state: FollowUpContactState
      note: string
    }) =>
      recordFollowUpOutcome(workspaceId, followUp.id, {
        state: nextState,
        note: nextNote,
        expected_version: followUp.version,
      }),
    () => {
      setChoice(null)
      setNote('')
    },
  )
  if (!choices.length) {
    return isOwner ? (
      <CorrectionForm workspaceId={workspaceId} followUp={followUp} />
    ) : null
  }
  // The choices change with the outcome. Send only one that is offered.
  const state = (choices.find((item) => item.value === choice) ?? choices[0])
    .value
  function submit(event: FormEvent) {
    event.preventDefault()
    record.mutate({ state, note })
  }
  return (
    <form className="grid gap-3" onSubmit={submit} noValidate>
      <fieldset disabled={record.isPending} className="grid gap-3">
        <SelectField
          id={`${id}-state`}
          label="Record outcome"
          value={state}
          onChange={(event) =>
            setChoice(event.target.value as FollowUpContactState)
          }
        >
          {choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </SelectField>
        <TextareaField
          id={`${id}-note`}
          label={state === 'no_response' ? 'Note (required)' : 'Note'}
          hint={
            state === 'no_response'
              ? 'A note is required for a no-response outcome.'
              : 'Optional. Kept on the outcome record.'
          }
          required={state === 'no_response'}
          maxLength={2000}
          rows={3}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </fieldset>
      {record.isError ? (
        <ActionError
          error={record.error}
          title="The outcome was not recorded"
          record="report"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          className={layout === 'page' ? 'hover:bg-primary' : ''}
          disabled={
            record.isPending || (state === 'no_response' && !note.trim())
          }
        >
          {record.isPending ? 'Recording…' : 'Record outcome'}
        </Button>
      </div>
    </form>
  )
}

function CorrectionForm({
  workspaceId,
  followUp,
}: {
  workspaceId: string
  followUp: FollowUpDetail
}) {
  const id = useId()
  const choices: FollowUpContactState[] = [
    'pending',
    'contacted',
    'confirmed',
    'still_affected',
    'no_response',
  ].filter(
    (value) => value !== followUp.outcome.state,
  ) as FollowUpContactState[]
  const [choice, setChoice] = useState<FollowUpContactState | null>(null)
  // The choices change with the outcome. Send only one that is offered.
  const state = choice && choices.includes(choice) ? choice : choices[0]
  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const mutation = useFollowUpMutation(
    workspaceId,
    ({
      state: nextState,
      note: nextNote,
      reason: nextReason,
    }: {
      state: FollowUpContactState
      note: string
      reason: string
    }) =>
      correctFollowUpOutcome(workspaceId, followUp.id, {
        state: nextState,
        note: nextNote,
        reason: nextReason,
        expected_version: followUp.version,
      }),
    () => {
      setChoice(null)
      setNote('')
      setReason('')
    },
  )
  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate({ state, note, reason })
  }
  return (
    <form
      aria-label="Correct outcome"
      className="grid gap-3"
      onSubmit={submit}
      noValidate
    >
      <p className="text-xs text-muted-foreground">
        As an owner you can correct a recorded outcome. A reason is required.
      </p>
      <fieldset disabled={mutation.isPending} className="grid gap-3">
        <SelectField
          id={`${id}-state`}
          label="Correct to"
          value={state}
          onChange={(event) =>
            setChoice(event.target.value as FollowUpContactState)
          }
        >
          {choices.map((value) => (
            <option key={value} value={value}>
              {contactStateLabels[value]}
            </option>
          ))}
        </SelectField>
        <TextareaField
          id={`${id}-note`}
          label={state === 'no_response' ? 'Note (required)' : 'Note'}
          required={state === 'no_response'}
          maxLength={2000}
          rows={3}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <TextareaField
          id={`${id}-reason`}
          label="Reason"
          hint="Required. Logged on the correction."
          required
          maxLength={2000}
          rows={2}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </fieldset>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The outcome was not corrected"
          record="report"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          disabled={
            mutation.isPending ||
            !reason.trim() ||
            (state === 'no_response' && !note.trim())
          }
        >
          {mutation.isPending ? 'Correcting…' : 'Correct outcome'}
        </Button>
      </div>
    </form>
  )
}
