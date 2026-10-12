import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Copy, Send } from 'lucide-react'
import {
  approveFollowUpNotification,
  editFollowUpNotification,
  type FollowUpDetail,
  type FollowUpNotification,
} from '@/api/follow-ups'
import { Button } from '@/components/ui/button'
import { ActionError } from '@/components/states/action-error'
import { fieldError } from '@/components/forms/field-error'
import { TextareaField } from '@/components/forms/field'
import { memberName } from '@/features/inbox/report-format'
import { cn } from '@/lib/utils'
import { useFollowUpMutation } from './follow-ups-mutation'
import { wrapLongText } from './follow-up-layout'

export function MessageEditor({
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
        hint="Edits are saved when you select Save edits. If a save fails, your text stays here."
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

export function MessagePreview({ message }: { message: string }) {
  return (
    <div className="grid gap-2 rounded-control border border-border bg-muted/30 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Exact message
      </p>
      <p className={cn(wrapLongText, 'whitespace-pre-wrap text-sm')}>
        {message}
      </p>
    </div>
  )
}
