import { useCallback, useState } from 'react'
import type { ManualReportInput } from '@/api/reports'

export type ReportDraft = Required<ManualReportInput>

export const emptyDraft: ReportDraft = {
  title: '',
  description: '',
  customer_label: '',
  customer_contact_reference: '',
  affected_version: '',
}

const draftKey = (workspaceId: string) => `rescribo:report-draft:${workspaceId}`

const isEmpty = (draft: ReportDraft) =>
  Object.values(draft).every((value) => !value.trim())

// Session storage keeps a draft across reloads and failed requests in this
// tab without leaving customer text on the device after the tab closes.
function readDraft(workspaceId: string): ReportDraft {
  try {
    const stored: unknown = JSON.parse(
      sessionStorage.getItem(draftKey(workspaceId)) ?? 'null',
    )
    if (typeof stored !== 'object' || stored === null) return emptyDraft
    const values = stored as Record<string, unknown>
    return Object.fromEntries(
      Object.keys(emptyDraft).map((key) => [
        key,
        typeof values[key] === 'string' ? values[key] : '',
      ]),
    ) as ReportDraft
  } catch {
    return emptyDraft
  }
}

function writeDraft(workspaceId: string, draft: ReportDraft) {
  try {
    if (isEmpty(draft)) sessionStorage.removeItem(draftKey(workspaceId))
    else sessionStorage.setItem(draftKey(workspaceId), JSON.stringify(draft))
  } catch {
    // Storage can be unavailable; the in-memory draft still survives failures.
  }
}

export function useReportDraft(workspaceId: string) {
  const [initial] = useState(() => readDraft(workspaceId))
  const [draft, setDraft] = useState(initial)
  const [restored, setRestored] = useState(() => !isEmpty(initial))

  const update = useCallback(
    (field: keyof ReportDraft, value: string) => {
      setDraft((current) => {
        const next = { ...current, [field]: value }
        writeDraft(workspaceId, next)
        return next
      })
    },
    [workspaceId],
  )

  const clear = useCallback(() => {
    writeDraft(workspaceId, emptyDraft)
    setDraft(emptyDraft)
    setRestored(false)
  }, [workspaceId])

  return { draft, restored, update, clear }
}
