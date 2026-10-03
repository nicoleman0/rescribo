import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Copy, Send } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  approveFollowUpNotification,
  cancelFollowUpNotification,
  changeFollowUpRecipient,
  correctFollowUpOutcome,
  draftFollowUpNotification,
  editFollowUpNotification,
  followUpKeys,
  getFollowUp,
  markFollowUpDelivered,
  recordFollowUpOutcome,
  sendFollowUpAgain,
  type FollowUpContactState,
  type FollowUpDetail,
  type FollowUpHistoryItem,
  type FollowUpNotification,
  type FollowUpRecipient,
} from '@/api/follow-ups'
import type { ApiError } from '@/api/request'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { touchTarget } from '@/components/layout/touch-target'
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from '@/components/states/async-states'
import { ActionError } from '@/components/states/action-error'
import { fieldError } from '@/components/forms/field-error'
import { SelectField, TextareaField } from '@/components/forms/field'
import { memberName, formatDate } from '@/features/inbox/report-format'
import { useMembers } from '@/features/inbox/use-members'
import { useWorkspace } from '@/components/auth/use-workspace'
import { cn } from '@/lib/utils'
import {
  contactBadgeClass,
  contactStateLabels,
  deliveryBadgeClass,
  deliveryStateLabels,
} from './follow-ups-format'
import { useFollowUpMutation } from './follow-ups-mutation'

const QUEUED_POLL_MS = 5_000

export function FollowUpDetailPanel({
  workspaceId,
  followUpId,
}: {
  workspaceId: string
  followUpId: string
}) {
  const membership = useWorkspace()
  const [params] = useSearchParams()
  const backTo = `/follow-ups${params.toString() ? `?${params.toString()}` : ''}`
  const detail = useQuery({
    queryKey: followUpKeys.detail(workspaceId, followUpId),
    queryFn: () => getFollowUp(workspaceId, followUpId),
    retry: (failures, error) =>
      (error as ApiError).status !== 404 && failures < 2,
    refetchInterval: (query) =>
      (
        query.state.data?.notification as
          FollowUpNotification | null | undefined
      )?.state === 'queued' ||
      (
        query.state.data?.notification as
          FollowUpNotification | null | undefined
      )?.send_in_progress === true
        ? QUEUED_POLL_MS
        : false,
    refetchIntervalInBackground: false,
  })
  return (
    <section
      aria-label="Follow-up detail"
      className="grid content-start gap-4 rounded-card border border-border bg-card p-4"
    >
      <Button asChild variant="ghost" size="sm" className="w-fit">
        <Link to={backTo}>
          <ArrowLeft aria-hidden="true" />
          Back to follow-ups
        </Link>
      </Button>
      {detail.isPending ? <LoadingState label="Loading follow-up" /> : null}
      {detail.isError && (detail.error as ApiError).status === 404 ? (
        <EmptyState
          title="Follow-up not found"
          description="It may belong to another workspace, or the link is wrong."
        />
      ) : null}
      {detail.isError && (detail.error as ApiError).status !== 404 ? (
        <ErrorState
          title="Could not load this follow-up"
          onRetry={() => void detail.refetch()}
          isRetrying={detail.isFetching}
        />
      ) : null}
      {detail.isSuccess ? (
        <FollowUpBody
          workspaceId={workspaceId}
          followUp={detail.data}
          isOwner={membership.role === 'owner'}
        />
      ) : null}
    </section>
  )
}

function FollowUpBody({
  workspaceId,
  followUp,
  isOwner,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  isOwner: boolean
}) {
  const notification = followUp.notification as FollowUpNotification | null
  return (
    <article className="grid gap-4">
      <FollowUpSummary followUp={followUp} notification={notification} />
      <Separator />
      <Destination recipient={followUp.recipient} />
      <Separator />
      <MessageSection
        workspaceId={workspaceId}
        followUp={followUp}
        notification={notification}
      />
      {notification && notification.state !== 'cancelled' ? (
        <>
          <Separator />
          <ContactSection
            workspaceId={workspaceId}
            followUp={followUp}
            isOwner={isOwner}
          />
        </>
      ) : null}
      {isOwner ? (
        <>
          <Separator />
          <RecipientForm workspaceId={workspaceId} followUp={followUp} />
        </>
      ) : null}
      <Separator />
      <FollowUpHistory followUp={followUp} />
    </article>
  )
}

function FollowUpSummary({
  followUp,
  notification,
}: {
  followUp: FollowUpDetail
  notification: FollowUpNotification | null
}) {
  return (
    <header className="grid gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            'rounded-pill px-2 py-0.5 text-xs font-medium',
            contactBadgeClass(followUp.outcome.state),
          )}
        >
          Contact: {contactStateLabels[followUp.outcome.state]}
        </span>
        {notification ? (
          <span
            className={cn(
              'rounded-pill px-2 py-0.5 text-xs font-medium',
              deliveryBadgeClass(notification.state),
            )}
          >
            Delivery: {deliveryStateLabels[notification.state]}
          </span>
        ) : (
          <span className="rounded-pill bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
            Not prepared
          </span>
        )}
        <span className="font-mono text-[11px] text-muted-foreground">
          v{followUp.version}
        </span>
      </div>
      <h2 className="text-base font-semibold break-words">
        {followUp.report.title}
      </h2>
      <p className="text-sm text-muted-foreground">
        Customer: {followUp.report.customer_label || '—'}
      </p>
      <p className="text-sm text-muted-foreground">
        Fix: {followUp.problem.fix_note || '—'}
      </p>
      {followUp.problem.fix_version ? (
        <p className="text-sm text-muted-foreground">
          Available in {followUp.problem.fix_version}
        </p>
      ) : null}
      {followUp.outcome.note ? (
        <p className="text-sm">
          <span className="text-muted-foreground">Outcome note: </span>
          {followUp.outcome.note}
        </p>
      ) : null}
    </header>
  )
}

function Destination({ recipient }: { recipient: FollowUpRecipient }) {
  const text = recipient.has_slack_link
    ? `Slack DM to ${memberName(recipient.member)}`
    : `Copy to send to ${memberName(recipient.member)}`
  return (
    <p className="text-sm text-muted-foreground">
      <span className="font-medium text-foreground">Destination:</span> {text}
    </p>
  )
}

function MessageSection({
  workspaceId,
  followUp,
  notification,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification | null
}) {
  if (!notification) {
    return <DraftSection workspaceId={workspaceId} followUp={followUp} />
  }
  if (notification.state === 'queued') {
    return <QueuedSection notification={notification} />
  }
  if (notification.state === 'sent') {
    return <SentSection notification={notification} />
  }
  if (notification.state === 'failed') {
    return (
      <FailedSection
        workspaceId={workspaceId}
        followUp={followUp}
        notification={notification}
      />
    )
  }
  if (notification.state === 'uncertain') {
    return (
      <UncertainSection
        workspaceId={workspaceId}
        followUp={followUp}
        notification={notification}
      />
    )
  }
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <MessageEditor
        workspaceId={workspaceId}
        followUp={followUp}
        notification={notification}
      />
    </section>
  )
}

function DraftSection({
  workspaceId,
  followUp,
}: {
  workspaceId: string
  followUp: FollowUpDetail
}) {
  const draft = useFollowUpMutation(workspaceId, () =>
    draftFollowUpNotification(workspaceId, followUp.id),
  )
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Customer message</h3>
      <p className="text-sm text-muted-foreground">
        The default message uses the report title, the approved fix, the
        version, and a link to the report in Rescribo. Nothing from other
        customers or the GitHub issue is included.
      </p>
      <Button
        className={cn('w-fit', touchTarget)}
        disabled={draft.isPending}
        onClick={() => draft.mutate(undefined)}
      >
        <Send aria-hidden="true" />
        {draft.isPending ? 'Preparing…' : 'Prepare message'}
      </Button>
      {draft.isError ? (
        <ActionError
          error={draft.error}
          title="The message was not prepared"
          record="report"
        />
      ) : null}
    </section>
  )
}

function QueuedSection({
  notification,
}: {
  notification: FollowUpNotification
}) {
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Send in progress</h3>
      <p className="text-sm text-muted-foreground">
        The message is queued. This page will refresh when the result is ready.
      </p>
      <MessagePreview message={notification.message} />
    </section>
  )
}

function SentSection({ notification }: { notification: FollowUpNotification }) {
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Message sent</h3>
      {notification.delivery_confirmed_by ? (
        <p className="text-sm text-muted-foreground">
          Delivery confirmed by {memberName(notification.delivery_confirmed_by)}
          .
        </p>
      ) : null}
      <MessagePreview message={notification.message} />
    </section>
  )
}

function FailedSection({
  workspaceId,
  followUp,
  notification,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification
}) {
  const [messageReady, setMessageReady] = useState(false)
  const approve = useFollowUpMutation(workspaceId, (draftVersion: number) =>
    approveFollowUpNotification(workspaceId, followUp.id, {
      notification_id: notification.id,
      draft_version: draftVersion,
    }),
  )
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Delivery failed</h3>
      {notification.safe_error ? (
        <p role="status" className="text-sm text-muted-foreground">
          {notification.safe_error}
        </p>
      ) : null}
      <MessageEditor
        workspaceId={workspaceId}
        followUp={followUp}
        notification={notification}
        onReadyChange={setMessageReady}
      />
      <div className="flex flex-wrap gap-2">
        <Button
          className={touchTarget}
          disabled={approve.isPending || !messageReady}
          onClick={() => approve.mutate(notification.draft_version)}
        >
          {approve.isPending ? 'Retrying…' : 'Retry sending'}
        </Button>
      </div>
      {approve.isError ? (
        <ActionError
          error={approve.error}
          title="The retry was not queued"
          record="report"
        />
      ) : null}
    </section>
  )
}

function UncertainSection({
  workspaceId,
  followUp,
  notification,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification
}) {
  const id = useId()
  const [confirmingAgain, setConfirmingAgain] = useState(false)
  const markDelivered = useFollowUpMutation(
    workspaceId,
    (draftVersion: number) =>
      markFollowUpDelivered(workspaceId, followUp.id, {
        notification_id: notification.id,
        draft_version: draftVersion,
      }),
  )
  const sendAgain = useFollowUpMutation(workspaceId, (draftVersion: number) =>
    sendFollowUpAgain(workspaceId, followUp.id, {
      notification_id: notification.id,
      draft_version: draftVersion,
      checked_slack: true,
    }),
  )
  const cancel = useFollowUpMutation(workspaceId, (draftVersion: number) =>
    cancelFollowUpNotification(workspaceId, followUp.id, {
      notification_id: notification.id,
      draft_version: draftVersion,
    }),
  )
  return (
    <section
      aria-label="Message"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Send uncertain</h3>
      <p className="text-sm text-muted-foreground">
        Slack may or may not have received the message. Check Slack before
        choosing what to do.
      </p>
      {notification.safe_error ? (
        <p role="status" className="text-sm text-muted-foreground">
          {notification.safe_error}
        </p>
      ) : null}
      <MessagePreview message={notification.message} />
      {notification.send_in_progress ? (
        <p role="status" className="text-sm text-muted-foreground">
          The worker is still resolving this send. Recovery actions will appear
          when reconciliation finishes.
        </p>
      ) : confirmingAgain ? (
        <Alert>
          <AlertTitle>I checked Slack</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>
              Confirm Slack does not show this message before sending again, so
              the customer does not get a duplicate.
            </span>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                className={touchTarget}
                disabled={sendAgain.isPending}
                onClick={() => {
                  sendAgain.mutate(notification.draft_version)
                  setConfirmingAgain(false)
                }}
              >
                {sendAgain.isPending ? 'Sending again…' : 'Send again'}
              </Button>
              <Button
                type="button"
                variant="outline"
                className={touchTarget}
                onClick={() => setConfirmingAgain(false)}
              >
                Cancel
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            className={touchTarget}
            disabled={markDelivered.isPending}
            onClick={() => markDelivered.mutate(notification.draft_version)}
          >
            {markDelivered.isPending ? 'Marking…' : 'Mark as delivered'}
          </Button>
          <Button
            variant="outline"
            className={touchTarget}
            disabled={sendAgain.isPending}
            onClick={() => setConfirmingAgain(true)}
          >
            Send again
          </Button>
          <Button
            variant="outline"
            className={touchTarget}
            disabled={cancel.isPending}
            onClick={() => cancel.mutate(notification.draft_version)}
          >
            {cancel.isPending ? 'Cancelling…' : 'Cancel send'}
          </Button>
        </div>
      )}
      {markDelivered.isError ? (
        <ActionError
          error={markDelivered.error}
          title="Could not mark as delivered"
          record="report"
        />
      ) : null}
      {sendAgain.isError ? (
        <ActionError
          error={sendAgain.error}
          title="The send was not retried"
          record="report"
        />
      ) : null}
      {cancel.isError ? (
        <ActionError
          error={cancel.error}
          title="The send was not cancelled"
          record="report"
        />
      ) : null}
      <span id={`${id}-copylabel`} className="sr-only">
        Copy the message to send by hand
      </span>
    </section>
  )
}

function MessageEditor({
  workspaceId,
  followUp,
  notification,
  onReadyChange,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification
  onReadyChange?: (ready: boolean) => void
}) {
  const [message, setMessage] = useState(notification.message)
  const initialised = useRef(false)
  useEffect(() => {
    if (!initialised.current) {
      setMessage(notification.message)
      initialised.current = true
    }
  }, [notification.message])
  const dirty = message !== notification.message
  const save = useFollowUpMutation(
    workspaceId,
    ({
      message: nextMessage,
      draftVersion,
    }: {
      message: string
      draftVersion: number
    }) =>
      editFollowUpNotification(workspaceId, followUp.id, {
        message: nextMessage,
        notification_id: notification.id,
        draft_version: draftVersion,
      }),
  )
  useEffect(() => {
    onReadyChange?.(!dirty && !save.isPending && !save.isError)
  }, [dirty, save.isPending, save.isError, onReadyChange])
  function submit(event: FormEvent) {
    event.preventDefault()
    save.mutate({ message, draftVersion: notification.draft_version })
  }
  return (
    <form className="grid gap-3" onSubmit={submit} noValidate>
      <TextareaField
        id="follow-up-message"
        label="Message"
        hint="Edited on a server too. Edits stay here when a save fails."
        maxLength={10000}
        rows={8}
        value={message}
        disabled={save.isPending}
        error={fieldError(save.error, 'message')}
        onChange={(event) => setMessage(event.target.value)}
      />
      {!dirty ? <MessagePreview message={notification.message} /> : null}
      {save.isError ? (
        <ActionError
          error={save.error}
          title="The message was not saved"
          record="report"
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="submit"
          variant="outline"
          className={touchTarget}
          disabled={save.isPending || !dirty}
        >
          {save.isPending ? 'Saving…' : 'Save edits'}
        </Button>
        <ApproveButton
          workspaceId={workspaceId}
          followUp={followUp}
          notification={notification}
          draftOverride={message}
          disabled={save.isPending || save.isError}
        />
      </div>
    </form>
  )
}

function ApproveButton({
  workspaceId,
  followUp,
  notification,
  draftOverride,
  disabled = false,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification
  draftOverride?: string
  disabled?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const approve = useFollowUpMutation(workspaceId, (draftVersion: number) =>
    approveFollowUpNotification(workspaceId, followUp.id, {
      notification_id: notification.id,
      draft_version: draftVersion,
    }),
  )
  const hasSlack = followUp.recipient.has_slack_link
  if (!hasSlack) {
    return (
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            className={touchTarget}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(
                  draftOverride ?? notification.message,
                )
                setCopied(true)
              } catch {
                setCopied(false)
              }
            }}
          >
            <Copy aria-hidden="true" />
            {copied ? 'Copied' : 'Copy message'}
          </Button>
          <span className="text-xs text-muted-foreground">
            {memberName(followUp.recipient.member)} has no Slack link. Outcomes
            below are recorded directly.
          </span>
        </div>
        {approve.isError ? (
          <ActionError
            error={approve.error}
            title="The message was not queued"
            record="report"
          />
        ) : null}
      </div>
    )
  }
  return (
    <div className="grid gap-2">
      <Button
        type="button"
        className={touchTarget}
        disabled={
          approve.isPending ||
          disabled ||
          (draftOverride !== undefined &&
            draftOverride !== notification.message)
        }
        onClick={() => approve.mutate(notification.draft_version)}
      >
        <Send aria-hidden="true" />
        {approve.isPending ? 'Sending…' : 'Send to Slack'}
      </Button>
      {approve.isError ? (
        <ActionError
          error={approve.error}
          title="The message was not queued"
          record="report"
        />
      ) : null}
    </div>
  )
}

function MessagePreview({ message }: { message: string }) {
  return (
    <div className="grid gap-2 rounded-control border border-border bg-muted/30 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Exact message
      </p>
      <p className="whitespace-pre-wrap break-words text-sm">{message}</p>
    </div>
  )
}

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

function ContactSection({
  workspaceId,
  followUp,
  isOwner,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  isOwner: boolean
}) {
  return (
    <section
      aria-label="Customer contact"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="font-medium">Customer contact</h3>
      <p className="text-sm text-muted-foreground">
        Outcome: {contactStateLabels[followUp.outcome.state]}.
      </p>
      {followUp.outcome.note ? (
        <p className="text-sm">
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
  const choices = choicesFor(followUp.outcome.state)
  const [state, setState] = useState<FollowUpContactState>(
    choices[0]?.value ?? 'pending',
  )
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
  )
  if (!choices.length) {
    return isOwner ? (
      <CorrectionForm workspaceId={workspaceId} followUp={followUp} />
    ) : null
  }
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
            setState(event.target.value as FollowUpContactState)
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
          className={touchTarget}
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
  const [state, setState] = useState<FollowUpContactState>(choices[0])
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
            setState(event.target.value as FollowUpContactState)
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
          className={touchTarget}
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

function RecipientForm({
  workspaceId,
  followUp,
}: {
  workspaceId: string
  followUp: FollowUpDetail
}) {
  const id = useId()
  const members = useMembers(workspaceId)
  const saved = followUp.recipient.member.id
  const [choice, setChoice] = useState<string | null>(null)
  const recipient = choice ?? saved
  const mutation = useFollowUpMutation(
    workspaceId,
    (newRecipientId: string) =>
      changeFollowUpRecipient(workspaceId, followUp.id, {
        new_recipient_id: newRecipientId,
      }),
    () => setChoice(null),
  )
  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(recipient)
  }
  return (
    <form
      aria-label="Change recipient"
      className="grid gap-2 rounded-card border border-border p-4"
      onSubmit={submit}
      noValidate
    >
      <h3 className="font-medium">Recipient</h3>
      <p className="text-xs text-muted-foreground">
        Owner-only. Cancels any unsent notification and logs the change. New
        recipients must be active members with a Slack link in this workspace.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1">
          <SelectField
            id={`${id}-recipient`}
            label="Recipient"
            value={recipient}
            disabled={mutation.isPending}
            error={fieldError(mutation.error, 'new_recipient_id')}
            onChange={(event) => setChoice(event.target.value)}
          >
            {members.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {memberName(member)}
              </option>
            ))}
            {members.data &&
            !members.data.some((member) => member.id === saved) ? (
              <option value={saved}>
                {memberName(followUp.recipient.member)}
              </option>
            ) : null}
          </SelectField>
        </div>
        <Button
          type="submit"
          variant="outline"
          className={cn('h-9', touchTarget)}
          disabled={mutation.isPending || recipient === saved}
        >
          {mutation.isPending ? 'Saving…' : 'Change recipient'}
        </Button>
      </div>
      {mutation.isError ? (
        <ActionError
          error={mutation.error}
          title="The recipient was not changed"
          record="report"
        />
      ) : null}
    </form>
  )
}

function FollowUpHistory({ followUp }: { followUp: FollowUpDetail }) {
  const history = (followUp.history ?? []) as FollowUpHistoryItem[]
  if (!history.length) return null
  return (
    <section
      aria-labelledby="follow-up-history"
      className="grid gap-3 rounded-card border border-border p-4"
    >
      <h2 id="follow-up-history" className="text-base font-semibold">
        History
      </h2>
      <ol className="grid gap-2 border-l border-border pl-4">
        {history.map((entry) => (
          <li key={entry.id} className="grid gap-0.5 text-sm">
            <span className="break-words">
              <span className="font-medium">
                {entry.actor ? memberName(entry.actor) : entry.actor_system}
              </span>{' '}
              {describeHistory(entry)}
            </span>
            <time
              dateTime={entry.created_at}
              className="font-mono text-xs text-muted-foreground"
            >
              {formatDate(entry.created_at)}
            </time>
          </li>
        ))}
      </ol>
    </section>
  )
}

function describeHistory(entry: FollowUpHistoryItem) {
  switch (entry.action) {
    case 'follow_up.notification_approved':
      return 'approved the message for sending'
    case 'follow_up.notification_sent':
      return 'recorded the send'
    case 'follow_up.notification_failed':
      return 'marked the send failed'
    case 'follow_up.notification_cancelled':
      return 'cancelled the send'
    case 'follow_up.outcome_recorded':
      return 'recorded the outcome'
    case 'follow_up.outcome_corrected':
      return 'corrected the outcome'
    case 'follow_up.recipient_changed':
      return 'changed the recipient'
    default:
      return 'updated the follow-up'
  }
}
