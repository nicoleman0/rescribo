import type { LucideIcon } from 'lucide-react'
import { CircleDot, Inbox, MessageSquareText, Settings } from 'lucide-react'

export type NavigationDestination = {
  label: string
  path: string
  icon: LucideIcon
}

/** The product screens, in sidebar order. The sidebar, the phone tab bar, and
 * the command palette all read this list. */
export const NAVIGATION_ITEMS: readonly NavigationDestination[] = [
  { label: 'Inbox', path: '/inbox', icon: Inbox },
  { label: 'Problems', path: '/problems', icon: CircleDot },
  { label: 'Follow-ups', path: '/follow-ups', icon: MessageSquareText },
  { label: 'Settings', path: '/settings', icon: Settings },
]
