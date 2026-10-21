import { toast } from 'sonner'
import { changeFollowUpRecipient, type FollowUpDetail } from '@/api/follow-ups'
import {
  MemberPicker,
  MemberPickerError,
} from '@/components/member-picker/member-picker'
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
  const members = useMembers(workspaceId)
  const mutation = useFollowUpMutation(
    workspaceId,
    (newRecipientId: string) =>
      changeFollowUpRecipient(workspaceId, followUp.id, {
        new_recipient_id: newRecipientId,
      }),
    (saved) =>
      toast.success(
        `Recipient changed to ${memberName(saved.recipient.member)}`,
      ),
    {
      followUpId: followUp.id,
      patch: (copy, recipientId) => {
        const member = members.data?.find((m) => m.id === recipientId)
        return member
          ? {
              ...copy,
              recipient: {
                member: { id: member.id, display_name: member.display_name },
                has_slack_link: member.has_slack_link,
              },
            }
          : copy
      },
    },
  )
  return (
    <section aria-label="Change recipient" className={useSectionClass('gap-2')}>
      <SectionHeading>Recipient</SectionHeading>
      <p className="text-xs text-muted-foreground">
        Owner-only. Cancels any unsent notification and logs the change. New
        recipients must be active members with a Slack link in this workspace.
      </p>
      <div>
        <MemberPicker
          label="Recipient"
          value={followUp.recipient.member.id}
          current={followUp.recipient.member}
          members={members}
          unavailableLabel="no Slack link"
          isUnavailable={(member) => !member.has_slack_link}
          pending={mutation.isPending}
          onChoose={(recipientId) =>
            mutation.mutateAsync(recipientId).catch((error: unknown) => {
              void members.refetch()
              throw error
            })
          }
          onClose={() => mutation.reset()}
          error={
            <MemberPickerError
              error={mutation.error}
              field="new_recipient_id"
              title="The recipient was not changed"
              record="report"
            />
          }
        />
      </div>
    </section>
  )
}
