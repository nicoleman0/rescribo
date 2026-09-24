import type { MemberSummary, SourceKind } from '@/api/reports'
import { sourceKinds } from './inbox-query'

const dateFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

export const formatDate = (value: string) => dateFormat.format(new Date(value))

export const memberName = (member: MemberSummary) =>
  member.full_name || member.email

export const sourceLabel = (kind: SourceKind) =>
  sourceKinds.find((item) => item.value === kind)?.label ?? kind
