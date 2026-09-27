import { csrf } from './auth'
import { apiRequest, queryString, type ApiError } from './request'
import type { components, operations } from './schema'

type Schemas = components['schemas']

export type ReportListItem = Schemas['ReportListItem']
export type ReportDetail = Schemas['ReportDetail']
export type ReportPage = Schemas['PaginatedReportListItemList']
export type MemberSummary = Schemas['MemberSummary']
export type ManualReportInput = Schemas['ManualReport']
export type TriageState = Schemas['TriageStateEnum']
export type SourceKind = Schemas['ReportSourceKindEnum']
export type ReportProvenance = Schemas['ReportProvenance']
export type ReportQuery = NonNullable<
  operations['workspaces_reports_list']['parameters']['query']
>

/** Inbox filters as sent to the API. Enum values stay unvalidated on the
 * client so the server response can drive the invalid-filters state. */
export type InboxQuery = Omit<ReportQuery, 'triage_state' | 'source_kind'> & {
  triage_state?: string
  source_kind?: string
}

export const reportKeys = {
  all: (workspaceId: string) => ['workspaces', workspaceId, 'reports'] as const,
  list: (workspaceId: string, query: InboxQuery) =>
    [...reportKeys.all(workspaceId), 'list', query] as const,
  detail: (workspaceId: string, reportId: string) =>
    [...reportKeys.all(workspaceId), 'detail', reportId] as const,
  members: (workspaceId: string) =>
    ['workspaces', workspaceId, 'members'] as const,
}

export const listReports = (workspaceId: string, query: InboxQuery) =>
  apiRequest<ReportPage>(
    `workspaces/${workspaceId}/reports/${queryString(query)}`,
  )

export const getReport = (workspaceId: string, reportId: string) =>
  apiRequest<ReportDetail>(`workspaces/${workspaceId}/reports/${reportId}/`)

export const listMembers = (workspaceId: string) =>
  apiRequest<MemberSummary[]>(`workspaces/${workspaceId}/members/`)

export async function createManualReport(
  workspaceId: string,
  input: ManualReportInput,
) {
  await csrf()
  return apiRequest<ReportDetail>(`workspaces/${workspaceId}/reports/`, input)
}

type ReportAction =
  'link' | 'create-problem' | 'unlink' | 'dismiss' | 'restore' | 'assign'

async function reportAction(
  workspaceId: string,
  reportId: string,
  action: ReportAction,
  input: unknown,
) {
  await csrf()
  return apiRequest<ReportDetail>(
    `workspaces/${workspaceId}/reports/${reportId}/${action}/`,
    input,
  )
}

export const linkReport = (
  workspaceId: string,
  reportId: string,
  input: Schemas['LinkReport'],
) => reportAction(workspaceId, reportId, 'link', input)

export const createProblemForReport = (
  workspaceId: string,
  reportId: string,
  input: Schemas['CreateProblemForReport'],
) => reportAction(workspaceId, reportId, 'create-problem', input)

export const assignReport = (
  workspaceId: string,
  reportId: string,
  input: Schemas['AssignReport'],
) => reportAction(workspaceId, reportId, 'assign', input)

export const transitionReport = (
  workspaceId: string,
  reportId: string,
  action: 'unlink' | 'dismiss' | 'restore',
  input: Schemas['Versioned'],
) => reportAction(workspaceId, reportId, action, input)

/** The current report sent with a 409, or undefined for other errors. */
export const conflictingReport = (error: ApiError) =>
  error.status === 409 ? (error.current as ReportDetail | undefined) : undefined
