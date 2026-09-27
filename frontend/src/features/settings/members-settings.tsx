import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getInvitations,
  getMembers,
  settingsKey,
  type Member,
} from '@/api/settings'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/states/async-states'
import { ConfirmAction } from './confirm-action'
import { useSettingsAction } from './use-settings-action'

export function MembersSettings({ workspaceId }: { workspaceId: string }) {
  const members = useQuery({
    queryKey: [...settingsKey(workspaceId), 'members'],
    queryFn: () => getMembers(workspaceId),
  })
  const invites = useQuery({
    queryKey: [...settingsKey(workspaceId), 'invitations'],
    queryFn: () => getInvitations(workspaceId),
  })
  const [email, setEmail] = useState('')
  const [now] = useState(() => Date.now())
  const create = useSettingsAction<{ accept_url: string }>(workspaceId)
  const revoke = useSettingsAction(workspaceId)
  return (
    <section className="grid gap-4" aria-labelledby="members-heading">
      <h2 id="members-heading" className="text-base font-semibold">
        Members and invitations
      </h2>
      {members.isPending ? <LoadingState label="Loading members" /> : null}
      {members.isError ? (
        <ErrorState
          title="Could not load members"
          onRetry={() => void members.refetch()}
        />
      ) : null}
      <ul className="divide-y divide-border">
        {members.data?.map((member) => (
          <MemberRow
            key={member.id}
            workspaceId={workspaceId}
            member={member}
          />
        ))}
      </ul>
      <form
        className="grid max-w-lg gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate(
            { path: 'invitations/', body: { email, role: 'member' } },
            { onSuccess: () => setEmail('') },
          )
        }}
      >
        <Field
          id="invite-email"
          label="Invite email"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={create.error?.fieldErrors?.email?.join(' ')}
          hint="Share the one-use link yourself. It expires after 48 hours."
        />
        <Button className="min-h-11 w-fit" disabled={create.isPending}>
          Create invitation
        </Button>
        {create.error ? (
          <ErrorState
            title="Invitation failed"
            description={create.error.message}
          />
        ) : null}
        {create.data ? (
          <Field
            id="invite-link"
            label="Invitation link"
            readOnly
            value={create.data.accept_url}
            onFocus={(event) => event.target.select()}
          />
        ) : null}
      </form>
      <h3 className="font-medium">Pending invitations</h3>
      {invites.isPending ? <LoadingState label="Loading invitations" /> : null}
      {invites.isError ? (
        <ErrorState
          title="Could not load invitations"
          onRetry={() => void invites.refetch()}
        />
      ) : null}
      {invites.data?.length === 0 ? (
        <p className="text-muted-foreground">No pending invitations.</p>
      ) : null}
      <ul className="grid gap-3">
        {invites.data?.map((invite) => (
          <li
            key={invite.id}
            className="flex flex-wrap items-center justify-between gap-3"
          >
            <span className="min-w-0 break-all">
              {invite.email}{' '}
              <span className="text-muted-foreground">
                {Date.parse(invite.expires_at) < now
                  ? 'Expired'
                  : `Expires ${new Date(invite.expires_at).toLocaleString()}`}
              </span>
            </span>
            <Button
              className="min-h-11"
              variant="outline"
              disabled={revoke.isPending}
              onClick={() =>
                revoke.mutate({
                  path: `invitations/${invite.id}/revoke/`,
                  body: {},
                })
              }
            >
              Revoke invitation
            </Button>
          </li>
        ))}
      </ul>
      {revoke.error ? (
        <ErrorState
          title="Could not revoke invitation"
          description={revoke.error.message}
        />
      ) : null}
    </section>
  )
}

function MemberRow({
  workspaceId,
  member,
}: {
  workspaceId: string
  member: Member
}) {
  const role = useSettingsAction(workspaceId)
  const reset = useSettingsAction<{ reset_url: string }>(workspaceId)
  return (
    <li className="grid gap-3 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium break-all">
            {member.full_name || member.email}
          </p>
          <p className="break-all text-muted-foreground">
            {member.email} · {member.role}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="min-h-11"
            disabled={role.isPending}
            onClick={() =>
              role.mutate({
                path: `memberships/${member.id}/role/`,
                body: { role: member.role === 'owner' ? 'member' : 'owner' },
              })
            }
          >
            {member.role === 'owner' ? 'Make member' : 'Make owner'}
          </Button>
          {member.role === 'member' ? (
            <Button
              variant="outline"
              className="min-h-11"
              disabled={reset.isPending}
              onClick={() =>
                reset.mutate({
                  path: `memberships/${member.id}/password-reset/`,
                  body: {},
                })
              }
            >
              Create password reset
            </Button>
          ) : null}
        </div>
      </div>
      <ConfirmAction
        workspaceId={workspaceId}
        path={`memberships/${member.id}/revoke/`}
        label={`Remove ${member.email}`}
        phrase="REMOVE"
        scope="This membership loses workspace access immediately. Reports and activity remain. The last active owner cannot be removed."
      />
      {role.error || reset.error ? (
        <ErrorState
          title="Member update failed"
          description={(role.error || reset.error)?.message}
        />
      ) : null}
      {reset.data ? (
        <Field
          id={`reset-${member.id}`}
          label="Password reset link"
          readOnly
          value={reset.data.reset_url}
          onFocus={(event) => event.target.select()}
        />
      ) : null}
    </li>
  )
}
