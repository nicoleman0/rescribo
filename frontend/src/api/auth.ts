import { apiRequest } from './request'

export const sessionQueryKey = ['auth', 'session'] as const

export type Session = {
  user: { id: string; email: string; full_name: string }
  memberships: {
    membership_id: string
    role: 'owner' | 'member'
    workspace: { id: string; name: string; slug: string }
  }[]
}

export const getSession = () => apiRequest<Session>('auth/session/')
export const login = (email: string, password: string) =>
  apiRequest<Session>('auth/login/', { email, password })
export const logout = () => apiRequest<void>('auth/logout/', {})
export const csrf = () => apiRequest<void>('auth/csrf/')
