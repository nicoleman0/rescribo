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

export const reportKeys = {
  all: (workspaceId: string) => ['workspaces', workspaceId, 'reports'] as const,
  list: (workspaceId: string, query: ReportQuery) =>
    [...reportKeys.all(workspaceId), 'list', query] as const,
  detail: (workspaceId: string, reportId: string) =>
    [...reportKeys.all(workspaceId), 'detail', reportId] as const,
  members: (workspaceId: string) =>
    ['workspaces', workspaceId, 'members'] as const,
}

function queryString(query: ReportQuery): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export const listReports = (workspaceId: string, query: ReportQuery) =>
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
