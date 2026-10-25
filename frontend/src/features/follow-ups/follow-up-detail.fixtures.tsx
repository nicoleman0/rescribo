import { screen } from '@testing-library/react'
import type { FollowUpDetail } from '@/api/follow-ups'
import { json, stubApi } from '@/test/render'
import { FollowUpDetailContent, FollowUpDetailPanel } from './follow-up-detail'

export const base = '/api/workspaces/ws-1/follow-ups/fu-1'
export const csrfPath = 'GET /api/auth/csrf/'

export const ada = {
  id: 'mem-2',
  display_name: 'Ada Lovelace',
  has_slack_link: true,
}
export const grace = {
  id: 'mem-3',
  display_name: 'Grace Hopper',
  has_slack_link: true,
}

export const routes = [
  {
    path: 'follow-ups/:followUpId',
    element: <FollowUpDetailPanel workspaceId="ws-1" followUpId="fu-1" />,
  },
  {
    path: 'follow-ups/:followUpId/page',
    element: (
      <FollowUpDetailContent
        workspaceId="ws-1"
        followUpId="fu-1"
        layout="page"
      />
    ),
  },
]

export function notification(
  state: 'draft' | 'queued' | 'failed' | 'uncertain' | 'sent' | 'cancelled',
  draftVersion = 1,
  overrides: Partial<FollowUpDetail['notification']> = {},
): NonNullable<FollowUpDetail['notification']> {
  return {
    id: 'op-1',
    send_in_progress: false,
    state,
    message: 'The fix for "CSV export fails" is available.',
    draft_version: draftVersion,
    safe_error: '',
    attempts: 1,
    approved_by: null,
    approved_at: null,
    sent_at: null,
    delivery_confirmed_by: null,
    delivery_confirmed_at: null,
    invalidated_at: null,
    invalidation_reason: '',
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-20T10:00:00Z',
    ...overrides,
  }
}

export function detail(
  overrides: Partial<FollowUpDetail> = {},
): FollowUpDetail {
  return {
    id: 'fu-1',
    report: {
      id: 'rep-1',
      title: 'CSV export fails',
      customer_label: 'Acme',
      triage_state: 'linked',
      version: 1,
      created_at: '2026-09-20T10:00:00Z',
    },
    problem: {
      id: 'prob-1',
      title: 'Exports fail',
      fix_note: 'Fix the parser',
      fix_version: '1.0',
      resolution_revision: 2,
    },
    recipient: { member: ada, has_slack_link: true },
    notification: null,
    outcome: { state: 'pending', note: '', at: null, by: null },
    version: 1,
    created_at: '2026-09-20T10:00:00Z',
    updated_at: '2026-09-20T10:00:00Z',
    history: [],
    can_record_outcome: true,
    ...overrides,
  }
}

export function stubDetail(overrides: Partial<FollowUpDetail> = {}) {
  document.cookie = 'csrftoken=csrf-token'
  stubApi({
    [csrfPath]: () => new Response(null, { status: 204 }),
    [`GET ${base}/`]: () => json(detail(overrides)),
  })
}

export const definitionOf = (term: string) =>
  screen.getAllByRole('term').find((dt) => dt.textContent === term)
    ?.nextElementSibling
