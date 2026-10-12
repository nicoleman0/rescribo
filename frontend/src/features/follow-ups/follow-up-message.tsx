import { useId, useState } from 'react'
import { Send } from 'lucide-react'
import {
  approveFollowUpNotification,
  cancelFollowUpNotification,
  draftFollowUpNotification,
  markFollowUpDelivered,
  sendFollowUpAgain,
  type FollowUpDetail,
  type FollowUpNotification,
} from '@/api/follow-ups'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { ActionError } from '@/components/states/action-error'
import { memberName } from '@/features/inbox/report-format'
import { useIsDemo } from '@/components/auth/use-workspace'
import { cn } from '@/lib/utils'
import { useFollowUpMutation } from './follow-ups-mutation'
import { useSectionClass, wrapLongText } from './follow-up-layout'
import { SectionHeading } from './follow-up-section-heading'
import { MessageEditor, MessagePreview } from './follow-up-message-editor'

export function MessageSection({
  workspaceId,
  followUp,
  notification,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  notification: FollowUpNotification | null
}) {
  const sectionClass = useSectionClass()
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
    <section aria-label="Message" className={sectionClass}>
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
    <section aria-label="Message" className={useSectionClass()}>
      <SectionHeading>Message to the employee</SectionHeading>
      <p className="text-sm text-muted-foreground">
        The default message uses the report title, the approved fix, the
        version, and a link to the report in Rescribo. Nothing from other
        customers or the GitHub issue is included.
      </p>
      {followUp.outcome.state !== 'pending' ? (
        <p className="text-sm text-muted-foreground">
          Customer contact is already recorded. Prepare a message only if{' '}
          {memberName(followUp.recipient.member)} still needs it.
        </p>
      ) : null}
      <Button
        className="w-fit"
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
    <section aria-label="Message" className={useSectionClass()}>
      <SectionHeading>Send in progress</SectionHeading>
      <p className="text-sm text-muted-foreground">
        The message is queued. This page will refresh when the result is ready.
      </p>
      <MessagePreview message={notification.message} />
    </section>
  )
}

function SentSection({ notification }: { notification: FollowUpNotification }) {
  const isDemo = useIsDemo()
  return (
    <section aria-label="Message" className={useSectionClass()}>
      <SectionHeading>
        {isDemo ? 'Message sent (simulated)' : 'Message sent'}
      </SectionHeading>
      {isDemo ? (
        <p className="text-sm text-muted-foreground">
          This is a demo workspace. No Slack message was sent.
        </p>
      ) : null}
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
    <section aria-label="Message" className={useSectionClass()}>
      <SectionHeading>Delivery failed</SectionHeading>
      {notification.safe_error ? (
        <p
          role="status"
          className={cn(wrapLongText, 'text-sm text-muted-foreground')}
        >
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
    <section aria-label="Message" className={useSectionClass()}>
      <SectionHeading>Send uncertain</SectionHeading>
      <p className="text-sm text-muted-foreground">
        Slack may or may not have received the message. Check Slack before
        choosing what to do.
      </p>
      {notification.safe_error ? (
        <p
          role="status"
          className={cn(wrapLongText, 'text-sm text-muted-foreground')}
        >
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
              the employee does not get a duplicate.
            </span>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
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
            disabled={markDelivered.isPending}
            onClick={() => markDelivered.mutate(notification.draft_version)}
          >
            {markDelivered.isPending ? 'Marking…' : 'Mark as delivered'}
          </Button>
          <Button
            variant="outline"
            disabled={sendAgain.isPending}
            onClick={() => setConfirmingAgain(true)}
          >
            Send again
          </Button>
          <Button
            variant="outline"
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
