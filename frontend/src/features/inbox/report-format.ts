import type { MemberSummary, SourceKind } from '@/api/reports'
import { sourceLabels } from './inbox-query'

const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

const timeFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' })

const thisYearFormat = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
})

const otherYearFormat = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

export const formatDate = (value: string) => dateFormat.format(new Date(value))

export const formatTime = (value: string) => timeFormat.format(new Date(value))

/** Fits a list column: the time this year, the year otherwise. */
export function formatShortDate(value: string, now = new Date()) {
  const date = new Date(value)
  return date.getFullYear() === now.getFullYear()
    ? thisYearFormat.format(date)
    : otherYearFormat.format(date)
}

export const memberName = (member: MemberSummary) => member.display_name

export function actorName({
  actor,
  actor_system,
}: {
  actor: MemberSummary | null
  actor_system: string
}) {
  if (actor) return memberName(actor)
  return (
    {
      slack_delivery: 'Slack delivery',
      github_webhook: 'GitHub',
      github_reconciliation: 'GitHub sync',
    }[actor_system] ?? 'System'
  )
}

export function memberInitials(member: MemberSummary) {
  const words = member.display_name.trim().split(/\s+/).filter(Boolean)
  return words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join('')
}

export const sourceLabel = (kind: SourceKind) => sourceLabels[kind]
