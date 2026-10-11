import { apiRequest } from './request'
import type { components } from './schema'

export const sessionQueryKey = ['auth', 'session'] as const
export const demoOfferQueryKey = ['auth', 'demo-offer'] as const

export type DemoCredentials = components['schemas']['DemoOffer']['credentials']

export type Session = {
  user: { id: string; email: string; full_name: string }
  memberships: {
    membership_id: string
    role: 'owner' | 'member'
    workspace: { id: string; name: string; slug: string; is_demo: boolean }
  }[]
}

export const getSession = () => apiRequest<Session>('auth/session/')
export const login = (email: string, password: string) =>
  apiRequest<Session>('auth/login/', { email, password })
export const logout = () => apiRequest<void>('auth/logout/', {})
export const csrf = () => apiRequest<void>('auth/csrf/')
export const getDemoOffer = () =>
  apiRequest<components['schemas']['DemoOffer']>('auth/demo/').then(
    (offer) => offer.credentials,
  )
