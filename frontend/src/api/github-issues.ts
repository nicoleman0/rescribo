import { csrf } from './auth'
import type { ProblemDetail } from './problems'
import { apiRequest } from './request'
import type { components } from './schema'

export type EngineeringIssue = components['schemas']['EngineeringIssue']
export type IssueDraft = components['schemas']['IssueDraftResult']
export type ExternalOperation = components['schemas']['ExternalOperation']
type Schemas = components['schemas']

const path = (workspaceId: string, problemId: string) =>
  `workspaces/${workspaceId}/problems/${problemId}/issue/`

export async function saveGitHubIssueDraft(
  workspaceId: string,
  problemId: string,
  input: {
    expected_version: number
    title?: string
    body?: string
    draft_id?: string
  },
) {
  await csrf()
  return apiRequest<IssueDraft>(
    `${path(workspaceId, problemId)}preview/`,
    input,
  )
}

export async function linkGitHubIssue(
  workspaceId: string,
  problemId: string,
  input: { expected_version: number; reference: string; replace: boolean },
) {
  await csrf()
  return apiRequest<ProblemDetail>(
    `${path(workspaceId, problemId)}link/`,
    input,
  )
}

export async function approveGitHubIssue(
  workspaceId: string,
  problemId: string,
  input: { draft_id: string; draft_version: number; approved: true },
) {
  await csrf()
  return apiRequest<Schemas['ExternalOperation']>(
    `${path(workspaceId, problemId)}approve/`,
    input,
  )
}

export const getGitHubOperation = (
  workspaceId: string,
  problemId: string,
  operationId: string,
) =>
  apiRequest<Schemas['ExternalOperation']>(
    `${path(workspaceId, problemId)}operations/${operationId}/`,
  )

export async function reconcileGitHubOperation(
  workspaceId: string,
  problemId: string,
  operationId: string,
  reference?: string,
) {
  await csrf()
  return apiRequest<Pick<ExternalOperation, 'id' | 'state'>>(
    `${path(workspaceId, problemId)}operations/${operationId}/reconcile/`,
    reference ? { reference } : {},
  )
}

export async function refreshGitHubIssue(
  workspaceId: string,
  problemId: string,
  input: { issue_id: string },
) {
  await csrf()
  return apiRequest<Schemas['IssueRefreshStatus']>(
    `${path(workspaceId, problemId)}refresh/`,
    input,
  )
}

export async function abandonGitHubOperation(
  workspaceId: string,
  problemId: string,
  operationId: string,
  reason: string,
) {
  await csrf()
  return apiRequest<ExternalOperation>(
    `${path(workspaceId, problemId)}operations/${operationId}/abandon/`,
    { reason },
  )
}
