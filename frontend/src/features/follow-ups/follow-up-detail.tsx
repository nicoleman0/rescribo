import { useContext } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Maximize2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  followUpKeys,
  getFollowUp,
  type FollowUpDetail,
  type FollowUpNotification,
} from '@/api/follow-ups'
import type { ApiError } from '@/api/request'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { memberName } from '@/features/inbox/report-format'
import { useWorkspace } from '@/components/auth/use-workspace'
import { PageTitle } from '@/components/layout/page-title'
import { cn } from '@/lib/utils'
import { FollowUpStatuses } from './follow-up-statuses'
import {
  FollowUpLayoutContext,
  wrapLongText,
  type FollowUpLayout,
} from './follow-up-layout'
import { MessageSection } from './follow-up-message'
import { ContactSection } from './follow-up-outcome'
import { RecipientForm } from './follow-up-recipient-form'
import { FollowUpHistory } from './follow-up-history'

const QUEUED_POLL_MS = 5_000

export function FollowUpDetailPanel({
  workspaceId,
  followUpId,
}: {
  workspaceId: string
  followUpId: string
}) {
  const [params] = useSearchParams()
  const search = params.toString()
  const backTo = `/follow-ups${search ? `?${search}` : ''}`
  const fullPage = `/follow-ups/${followUpId}/page${search ? `?${search}` : ''}`
  return (
    <section
      aria-label="Follow-up detail"
      className="grid content-start gap-4 rounded-card surface-raised p-4 shadow-elevation-2"
    >
      <div className="flex items-center justify-between gap-2">
        <Button asChild variant="ghost" size="sm" className="w-fit">
          <Link to={backTo}>
            <ArrowLeft aria-hidden="true" />
            Back to follow-ups
          </Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link to={fullPage}>
            <Maximize2 aria-hidden="true" />
            Open full page
          </Link>
        </Button>
      </div>
      <FollowUpDetailContent
        workspaceId={workspaceId}
        followUpId={followUpId}
        layout="panel"
      />
    </section>
  )
}

export function FollowUpDetailContent({
  workspaceId,
  followUpId,
  layout,
}: {
  workspaceId: string
  followUpId: string
  layout: FollowUpLayout
}) {
  const membership = useWorkspace()
  const detail = useQuery({
    queryKey: followUpKeys.detail(workspaceId, followUpId),
    queryFn: () => getFollowUp(workspaceId, followUpId),
    retry: (failures, error) =>
      ![403, 404].includes((error as ApiError).status ?? 0) && failures < 2,
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
    <FollowUpLayoutContext.Provider value={layout}>
      {layout === 'page' ? (
        <PageTitle title={detail.data?.report.title ?? 'Follow-ups'} />
      ) : null}
      {detail.isPending ? <LoadingState label="Loading follow-up" /> : null}
      {detail.isError && (detail.error as ApiError).status === 404 ? (
        <EmptyState
          title="Follow-up not found"
          description="It may belong to another workspace, or the link is wrong."
        />
      ) : null}
      {detail.isError && (detail.error as ApiError).status === 403 ? (
        <EmptyState
          title="Follow-up access removed"
          description="You no longer have access to this follow-up."
        />
      ) : null}
      {detail.isError &&
      ![403, 404].includes((detail.error as ApiError).status ?? 0) &&
      !detail.data ? (
        <ErrorState
          title="Could not load this follow-up"
          onRetry={() => void detail.refetch()}
          isRetrying={detail.isFetching}
        />
      ) : null}
      {detail.isError &&
      detail.data &&
      ![403, 404].includes((detail.error as ApiError).status ?? 0) ? (
        <ErrorState
          title="Could not refresh this follow-up"
          description="Your open changes are still here. Retry to check for updates."
          onRetry={() => void detail.refetch()}
          isRetrying={detail.isFetching}
        />
      ) : null}
      {detail.data &&
      !(
        detail.isError &&
        [403, 404].includes((detail.error as ApiError).status ?? 0)
      ) ? (
        <ReadyState>
          <FollowUpBody
            workspaceId={workspaceId}
            followUp={detail.data}
            isOwner={membership.role === 'owner'}
            layout={layout}
          />
        </ReadyState>
      ) : null}
    </FollowUpLayoutContext.Provider>
  )
}

function FollowUpBody({
  workspaceId,
  followUp,
  isOwner,
  layout,
}: {
  workspaceId: string
  followUp: FollowUpDetail
  isOwner: boolean
  layout: FollowUpLayout
}) {
  const notification = followUp.notification as FollowUpNotification | null
  const message = (
    <MessageSection
      workspaceId={workspaceId}
      followUp={followUp}
      notification={notification}
    />
  )
  const contact = (
    <ContactSection
      workspaceId={workspaceId}
      followUp={followUp}
      isOwner={isOwner}
    />
  )
  const recipient = isOwner ? (
    <RecipientForm workspaceId={workspaceId} followUp={followUp} />
  ) : null
  const history = <FollowUpHistory followUp={followUp} />
  return layout === 'panel' ? (
    <article className="grid gap-4">
      <FollowUpSummary followUp={followUp} notification={notification} />
      <Separator />
      {message}
      <Separator />
      {contact}
      {recipient ? (
        <>
          <Separator />
          {recipient}
        </>
      ) : null}
      <Separator />
      {history}
    </article>
  ) : (
    <article className="grid gap-4">
      <FollowUpSummary followUp={followUp} notification={notification} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid content-start gap-4">
          {message}
          {contact}
        </div>
        <div className="grid content-start gap-4">
          {recipient}
          {history}
        </div>
      </div>
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
  const { recipient } = followUp
  const layout = useContext(FollowUpLayoutContext)
  const Title = layout === 'panel' ? 'h2' : 'h1'
  return (
    <header className="grid gap-3">
      <FollowUpStatuses
        delivery={notification?.state ?? null}
        outcome={followUp.outcome.state}
      />
      <div className="flex items-baseline justify-between gap-3">
        <Title
          className={cn(
            'min-w-0 font-semibold break-words',
            layout === 'page' ? 'text-xl' : 'text-base',
          )}
        >
          {followUp.report.title}
        </Title>
        <span className="font-mono text-[11px] text-muted-foreground">
          v{followUp.version}
        </span>
      </div>
      <dl className="grid grid-cols-[6rem_minmax(0,1fr)] gap-x-3 gap-y-2 text-sm">
        <dt className="text-muted-foreground">Customer</dt>
        <dd className="break-words">{followUp.report.customer_label || '—'}</dd>
        <dt className="text-muted-foreground">Fix</dt>
        <dd className="break-words">{followUp.problem.fix_note || '—'}</dd>
        {followUp.problem.fix_version ? (
          <>
            <dt className="text-muted-foreground">Available in</dt>
            <dd className="break-words">{followUp.problem.fix_version}</dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">Destination</dt>
        <dd className="break-words">
          {recipient.has_slack_link
            ? `Slack DM to ${memberName(recipient.member)}`
            : `Copy to send to ${memberName(recipient.member)}`}
        </dd>
        {followUp.outcome.note ? (
          <>
            <dt className="text-muted-foreground">Outcome note</dt>
            <dd className={wrapLongText}>{followUp.outcome.note}</dd>
          </>
        ) : null}
      </dl>
    </header>
  )
}
