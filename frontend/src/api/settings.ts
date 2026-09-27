import type { components } from './schema'
import { apiRequest } from './request'

export type Connection = components['schemas']['Connection']
export type Member = components['schemas']['MembershipOutput']
export type Invitation = components['schemas']['InvitationListItem']
export const settingsKey = (workspaceId: string) =>
  ['settings', workspaceId] as const
export const settingsPath = (workspaceId: string, path: string) =>
  `workspaces/${workspaceId}/${path}`
export const getConnections = (workspaceId: string) =>
  apiRequest<Connection[]>(settingsPath(workspaceId, 'connections/'))
export const getMembers = (workspaceId: string) =>
  apiRequest<Member[]>(settingsPath(workspaceId, 'memberships/'))
export const getInvitations = (workspaceId: string) =>
  apiRequest<Invitation[]>(settingsPath(workspaceId, 'invitations/'))
