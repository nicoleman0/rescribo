import type { InboxQuery, SourceKind, TriageState } from '@/api/reports'

export const triageStates: { value: TriageState; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'linked', label: 'Linked' },
  { value: 'dismissed', label: 'Dismissed' },
]

export const sourceKinds: { value: SourceKind; label: string }[] = [
  { value: 'slack', label: 'Slack' },
  { value: 'manual', label: 'Manual entry' },
]

export const UNASSIGNED = 'unassigned'

const filterKeys = [
  'q',
  'customer',
  'triage_state',
  'assignee',
  'source_kind',
] as const

export type FilterKey = (typeof filterKeys)[number]

/** Read inbox filters from the URL. Enum values pass through unvalidated so
 * the API response can drive the invalid-filters state. */
export function queryFromParams(params: URLSearchParams): InboxQuery {
  const page = Number.parseInt(params.get('page') ?? '', 10)
  return {
    q: params.get('q')?.trim() || undefined,
    customer: params.get('customer')?.trim() || undefined,
    triage_state: params.get('triage_state')?.trim() || undefined,
    assignee: params.get('assignee') || undefined,
    source_kind: params.get('source_kind')?.trim() || undefined,
    page: Number.isInteger(page) && page > 1 ? page : undefined,
  }
}

export function hasActiveFilters(query: InboxQuery): boolean {
  return filterKeys.some((key) => Boolean(query[key]))
}

/** Apply filter changes and return to the first page of results. */
export function withFilters(
  params: URLSearchParams,
  changes: Partial<Record<FilterKey, string>>,
): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(changes)) {
    if (value?.trim()) next.set(key, value.trim())
    else next.delete(key)
  }
  next.delete('page')
  return next
}

export function withoutFilters(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const key of [...filterKeys, 'page']) next.delete(key)
  return next
}

export function withPage(
  params: URLSearchParams,
  page: number,
): URLSearchParams {
  const next = new URLSearchParams(params)
  if (page > 1) next.set('page', String(page))
  else next.delete('page')
  return next
}
