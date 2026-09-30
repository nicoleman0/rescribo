import { csrf } from './auth'
import { apiRequest, queryString, type ApiError } from './request'
import type { components, operations } from './schema'

type Schemas = components['schemas']

export type ProblemListItem = Schemas['ProblemListItem']
export type ProblemDetail = Schemas['ProblemDetail']
export type ProblemPage = Schemas['PaginatedProblemListItemList']
export type ProblemState = Schemas['ProblemStateEnum']
export type ProblemActivity = Schemas['ProblemActivity']
export type ProblemActivityPage = Schemas['PaginatedProblemActivityList']
export type ProblemReportPage = Schemas['PaginatedReportDetailList']
export type ProblemQuery = NonNullable<
  operations['workspaces_problems_list']['parameters']['query']
>

export const problemKeys = {
  githubOperation: (
    workspaceId: string,
    problemId: string,
    operationId: string,
  ) =>
    [
      ...problemKeys.detail(workspaceId, problemId),
      'github-operation',
      operationId,
    ] as const,
  all: (workspaceId: string) =>
    ['workspaces', workspaceId, 'problems'] as const,
  list: (workspaceId: string, query: ProblemQuery) =>
    [...problemKeys.all(workspaceId), 'list', query] as const,
  detail: (workspaceId: string, problemId: string) =>
    [...problemKeys.all(workspaceId), 'detail', problemId] as const,
  reports: (workspaceId: string, problemId: string, page: number) =>
    [...problemKeys.detail(workspaceId, problemId), 'reports', page] as const,
  activity: (workspaceId: string, problemId: string, page: number) =>
    [...problemKeys.detail(workspaceId, problemId), 'activity', page] as const,
}

const problemPath = (workspaceId: string, problemId: string) =>
  `workspaces/${workspaceId}/problems/${problemId}/`

export const listProblems = (workspaceId: string, query: ProblemQuery) =>
  apiRequest<ProblemPage>(
    `workspaces/${workspaceId}/problems/${queryString(query)}`,
  )

export const getProblem = (workspaceId: string, problemId: string) =>
  apiRequest<ProblemDetail>(problemPath(workspaceId, problemId))

export const listProblemReports = (
  workspaceId: string,
  problemId: string,
  page: number,
) =>
  apiRequest<ProblemReportPage>(
    `${problemPath(workspaceId, problemId)}reports/${queryString({ page: page > 1 ? page : undefined })}`,
  )

export const listProblemActivity = (
  workspaceId: string,
  problemId: string,
  page: number,
) =>
  apiRequest<ProblemActivityPage>(
    `${problemPath(workspaceId, problemId)}activity/${queryString({ page: page > 1 ? page : undefined })}`,
  )

export async function editProblem(
  workspaceId: string,
  problemId: string,
  input: Schemas['ProblemEdit'],
) {
  await csrf()
  return apiRequest<ProblemDetail>(
    `${problemPath(workspaceId, problemId)}edit/`,
    input,
  )
}

export async function confirmProblemFix(
  workspaceId: string,
  problemId: string,
  input: Schemas['FixConfirmation'],
) {
  await csrf()
  return apiRequest<ProblemDetail>(
    `${problemPath(workspaceId, problemId)}confirm-fix/`,
    input,
  )
}
export async function assignProblemOwner(
  workspaceId: string,
  problemId: string,
  input: Schemas['ProblemOwner'],
) {
  await csrf()
  return apiRequest<ProblemDetail>(
    `${problemPath(workspaceId, problemId)}assign-owner/`,
    input,
  )
}

/** The current problem sent with a 409, or undefined for other errors. */
export const conflictingProblem = (error: ApiError) =>
  error.status === 409
    ? (error.current as ProblemDetail | undefined)
    : undefined
