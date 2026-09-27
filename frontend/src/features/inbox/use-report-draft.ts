import { useCallback, useEffect, useState } from 'react'
import type { ManualReportInput } from '@/api/reports'

export type ReportDraft = Required<Omit<ManualReportInput, 'submission_key'>>

type StoredDraft = ReportDraft & Pick<ManualReportInput, 'submission_key'>

export const emptyDraft: ReportDraft = {
  title: '',
  description: '',
  customer_label: '',
  customer_contact_reference: '',
  affected_version: '',
}

const draftKey = (workspaceId: string) => `rescribo:report-draft:${workspaceId}`
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const isEmpty = (draft: ReportDraft) =>
  Object.values(draft).every((value) => !value.trim())

function readDraft(workspaceId: string): StoredDraft {
  let values: Record<string, unknown> = {}
  try {
    const stored: unknown = JSON.parse(
      sessionStorage.getItem(draftKey(workspaceId)) ?? 'null',
    )
    if (
      typeof stored === 'object' &&
      stored !== null &&
      !Array.isArray(stored)
    ) {
      values = stored as Record<string, unknown>
    }
  } catch {
    // Storage can be unavailable; the mounted page still keeps its draft.
  }
  const fields = Object.fromEntries(
    Object.keys(emptyDraft).map((key) => [
      key,
      typeof values[key] === 'string' ? values[key] : '',
    ]),
  ) as ReportDraft
  return {
    ...fields,
    submission_key:
      typeof values.submission_key === 'string' &&
      uuid.test(values.submission_key)
        ? values.submission_key
        : crypto.randomUUID(),
  }
}

function writeDraft(workspaceId: string, draft: StoredDraft | null) {
  try {
    if (draft === null) sessionStorage.removeItem(draftKey(workspaceId))
    else sessionStorage.setItem(draftKey(workspaceId), JSON.stringify(draft))
  } catch {
    // Failed storage writes must not prevent retrying the in-memory draft.
  }
}

export function useReportDraft(workspaceId: string) {
  const [initial] = useState(() => readDraft(workspaceId))
  const { submission_key: initialKey, ...initialFields } = initial
  const [draft, setDraft] = useState<ReportDraft>(initialFields)
  const [submissionKey, setSubmissionKey] = useState(initialKey)
  const [restored, setRestored] = useState(() => !isEmpty(initialFields))

  useEffect(() => {
    writeDraft(workspaceId, initial)
  }, [workspaceId, initial])

  const update = useCallback(
    (field: keyof ReportDraft, value: string) => {
      const next = { ...draft, [field]: value }
      setDraft(next)
      writeDraft(workspaceId, { ...next, submission_key: submissionKey })
    },
    [draft, submissionKey, workspaceId],
  )

  const prepareSubmission = useCallback((): ManualReportInput => {
    const input = { ...draft, submission_key: submissionKey }
    writeDraft(workspaceId, input)
    return input
  }, [draft, submissionKey, workspaceId])

  const clear = useCallback(() => {
    writeDraft(workspaceId, null)
    setDraft(emptyDraft)
    setSubmissionKey(crypto.randomUUID())
    setRestored(false)
  }, [workspaceId])

  return { draft, restored, update, clear, prepareSubmission }
}
