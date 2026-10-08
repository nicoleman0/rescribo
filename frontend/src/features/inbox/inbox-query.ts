import type { InboxQuery, SourceKind, TriageState } from '@/api/reports'

export const triageLabels: Record<TriageState, string> = {
  new: 'New',
  linked: 'Linked',
  dismissed: 'Dismissed',
}

export const sourceLabels: Record<SourceKind, string> = {
  slack: 'Slack',
  manual: 'Manual entry',
}

export const triageStates = (Object.keys(triageLabels) as TriageState[]).map(
  (value) => ({ value, label: triageLabels[value] }),
)

export const sourceKinds = (Object.keys(sourceLabels) as SourceKind[]).map(
  (value) => ({ value, label: sourceLabels[value] }),
)

export const UNASSIGNED = 'unassigned'

export const INBOX_REFRESH_MS = 30_000

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

/** Filters behind the phone Filters button; report search stays visible. */
export function hiddenFilterCount(query: InboxQuery): number {
  return filterKeys.filter((key) => key !== 'q' && Boolean(query[key])).length
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
