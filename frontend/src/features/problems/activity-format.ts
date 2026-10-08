import type { ProblemActivity } from '@/api/problems'

export type ActivityItem =
  | { kind: 'entry'; entry: ProblemActivity }
  | { kind: 'links'; entries: ProblemActivity[] }

// Links further apart than this are separate decisions, not one batch.
const BATCH_GAP_MS = 10 * 60 * 1000

const isPlainLink = (entry: ProblemActivity) =>
  entry.action === 'report.linked' && !entry.from_problem

const sameActor = (a: ProblemActivity, b: ProblemActivity) =>
  a.actor?.id === b.actor?.id && a.actor_system === b.actor_system

const withinGap = (a: ProblemActivity, b: ProblemActivity) =>
  Math.abs(Date.parse(a.created_at) - Date.parse(b.created_at)) <= BATCH_GAP_MS

/** Fold consecutive links of reports by one actor into one item. Entries keep
 * the API's order, newest first. */
export function groupActivity(entries: ProblemActivity[]): ActivityItem[] {
  const items: ActivityItem[] = []
  for (const entry of entries) {
    const last = items.at(-1)
    const previous = last?.kind === 'links' ? last.entries.at(-1) : last?.entry
    if (
      last &&
      previous &&
      isPlainLink(entry) &&
      isPlainLink(previous) &&
      sameActor(entry, previous) &&
      withinGap(entry, previous)
    ) {
      if (last.kind === 'links') last.entries.push(entry)
      else
        items[items.length - 1] = { kind: 'links', entries: [previous, entry] }
      continue
    }
    items.push({ kind: 'entry', entry })
  }
  return items
}

const fieldLabels: Record<string, string> = {
  title: 'title',
  summary: 'summary',
  owner: 'owner',
  state: 'status',
}

/** Describe a `problem.updated` entry from its changed field names. */
export function describeUpdate(fields: string[]): string {
  const changed = fields
    .filter((name) => name !== 'needs_review')
    .map((name) => fieldLabels[name] ?? name.replaceAll('_', ' '))
  const parts = []
  if (changed.length) parts.push(`changed the ${changed.join(' and ')}`)
  if (fields.includes('needs_review'))
    parts.push('flagged the problem for review')
  return parts.join(' and ') || 'updated the problem'
}
