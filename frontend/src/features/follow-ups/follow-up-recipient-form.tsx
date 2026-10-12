import { useId, useState, type FormEvent } from 'react'
import { changeFollowUpRecipient, type FollowUpDetail } from '@/api/follow-ups'
import { Button } from '@/components/ui/button'
import { ActionError } from '@/components/states/action-error'
import { fieldError } from '@/components/forms/field-error'
import { SelectField } from '@/components/forms/field'
import { memberName } from '@/features/inbox/report-format'
import { useMembers } from '@/features/inbox/use-members'
import { useFollowUpMutation } from './follow-ups-mutation'
import { useSectionClass } from './follow-up-layout'
import { SectionHeading } from './follow-up-section-heading'

export function RecipientForm({
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
    mutation.mutate(recipient, { onError: () => void members.refetch() })
  }
  return (
    <form
      aria-label="Change recipient"
      className={useSectionClass('gap-2')}
      onSubmit={submit}
      noValidate
    >
      <SectionHeading>Recipient</SectionHeading>
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
              <option
                key={member.id}
                value={member.id}
                disabled={!member.has_slack_link && member.id !== saved}
              >
                {memberName(member)}
                {member.has_slack_link ? '' : ' (no Slack link)'}
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
          className="h-9"
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
