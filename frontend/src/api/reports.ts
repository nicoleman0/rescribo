import { csrf } from './auth'
import { apiRequest } from './request'
import type { components, operations } from './schema'

type Schemas = components['schemas']

export type ReportListItem = Schemas['ReportListItem']
export type ReportDetail = Schemas['ReportDetail']
export type ReportPage = Schemas['PaginatedReportListItemList']
export type MemberSummary = Schemas['MemberSummary']
export type ManualReportInput = Schemas['ManualReport']
export type TriageState = Schemas['TriageStateEnum']
export type SourceKind = Schemas['ReportSourceKindEnum']
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

function queryString(query: InboxQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
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
