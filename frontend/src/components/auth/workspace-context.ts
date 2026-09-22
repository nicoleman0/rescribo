import { createContext } from 'react'
import type { Session } from '@/api/auth'

export const WorkspaceContext = createContext<
  Session['memberships'][number] | null
>(null)
