import { csrf } from './auth'
import { apiRequest, queryString, type ApiError } from './request'
import type { components, operations } from './schema'

type Schemas = components['schemas']

export type FollowUpListItem = Schemas['FollowUpListItem']
export type FollowUpDetail = Schemas['FollowUpDetail']
export type FollowUpPage = Schemas['PaginatedFollowUpListItemList']
export type FollowUpBucket = NonNullable<
  operations['workspaces_follow_ups_list']['parameters']['query']
>['bucket']
export type FollowUpContactState = Schemas['FollowUpContactStateEnum']
export type FollowUpNotificationState =
  Schemas['ReportNotificationOperationStateEnum']
export type FollowUpRecipient = Schemas['FollowUpRecipient']
export type FollowUpProblemSummary = Schemas['FollowUpProblemSummary']
export type FollowUpReportSummary = Schemas['FollowUpReportSummary']
export type FollowUpOutcome = Schemas['FollowUpOutcome']

/** The one non-cancelled notification row, or null when not yet prepared.
 * Mirrors `FollowUpNotificationSerializer` in the backend. */
export interface FollowUpNotification {
  id: string
  send_in_progress: boolean
  state: FollowUpNotificationState
  message: string
  draft_version: number
  safe_error: string
  attempts: number
  approved_by: Schemas['MemberSummary'] | null
  approved_at: string | null
  sent_at: string | null
  delivery_confirmed_by: Schemas['MemberSummary'] | null
  delivery_confirmed_at: string | null
  invalidated_at: string | null
  invalidation_reason: string
  created_at: string
  updated_at: string
}

/** A history entry as resolved by `FollowUpHistoryItemSerializer`. */
export interface FollowUpHistoryItem {
  id: string
  action: string
  actor: Schemas['MemberSummary'] | null
  actor_system: string
  created_at: string
}

export const followUpKeys = {
  all: (workspaceId: string) =>
    ['workspaces', workspaceId, 'follow-ups'] as const,
  list: (workspaceId: string, bucket: FollowUpBucket | null, page: number) =>
    [...followUpKeys.all(workspaceId), 'list', bucket, page] as const,
  detail: (workspaceId: string, followUpId: string) =>
    [...followUpKeys.all(workspaceId), 'detail', followUpId] as const,
}

export const listFollowUps = (
  workspaceId: string,
  bucket: FollowUpBucket | null,
  page = 1,
) =>
  apiRequest<FollowUpPage>(
    `workspaces/${workspaceId}/follow-ups/${queryString({
      bucket: bucket ?? undefined,
      page: page > 1 ? page : undefined,
    })}`,
  )

export const getFollowUp = (workspaceId: string, followUpId: string) =>
  apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/`,
  )

export async function draftFollowUpNotification(
  workspaceId: string,
  followUpId: string,
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/`,
    {},
  )
}

export async function editFollowUpNotification(
  workspaceId: string,
  followUpId: string,
  input: { message: string; notification_id: string; draft_version: number },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/edit/`,
    input,
  )
}

export async function approveFollowUpNotification(
  workspaceId: string,
  followUpId: string,
  input: { notification_id: string; draft_version: number },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/approve/`,
    input,
  )
}

export async function markFollowUpDelivered(
  workspaceId: string,
  followUpId: string,
  input: { notification_id: string; draft_version: number },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/mark-delivered/`,
    input,
  )
}

export async function sendFollowUpAgain(
  workspaceId: string,
  followUpId: string,
  input: {
    notification_id: string
    draft_version: number
    checked_slack: boolean
  },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/send-again/`,
    input,
  )
}

export async function cancelFollowUpNotification(
  workspaceId: string,
  followUpId: string,
  input: { notification_id: string; draft_version: number },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/notification/cancel/`,
    input,
  )
}

export async function recordFollowUpOutcome(
  workspaceId: string,
  followUpId: string,
  input: {
    state: FollowUpContactState
    note?: string
    expected_version: number
  },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/outcome/`,
    input,
  )
}

export async function correctFollowUpOutcome(
  workspaceId: string,
  followUpId: string,
  input: {
    state: FollowUpContactState
    note?: string
    reason: string
    expected_version: number
  },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/outcome/correct/`,
    input,
  )
}

export async function changeFollowUpRecipient(
  workspaceId: string,
  followUpId: string,
  input: { new_recipient_id: string },
) {
  await csrf()
  return apiRequest<FollowUpDetail>(
    `workspaces/${workspaceId}/follow-ups/${followUpId}/recipient/`,
    input,
  )
}

/** The current follow-up sent with a 409, or undefined for other errors. */
export const conflictingFollowUp = (error: ApiError) =>
  error.status === 409
    ? (error.current as FollowUpDetail | undefined)
    : undefined
