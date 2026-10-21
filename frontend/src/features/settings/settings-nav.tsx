import { useEffect, useRef } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { touchTarget } from '@/components/layout/touch-target'
import { cn } from '@/lib/utils'
import { sectionsForRole } from './sections'

export function SettingsNav({ role }: { role: 'owner' | 'member' }) {
  const { pathname } = useLocation()
  const active = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    active.current?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
  }, [pathname])
  return (
    <nav aria-label="Settings sections" className="min-w-0 md:w-44 md:shrink-0">
      <ul className="flex gap-1 overflow-x-auto md:grid md:overflow-visible">
        {sectionsForRole(role).map(({ slug, label }) => (
          <li key={slug} className="shrink-0">
            <NavLink
              ref={pathname === `/settings/${slug}` ? active : undefined}
              to={`/settings/${slug}`}
              className={({ isActive }) =>
                cn(
                  'flex items-center rounded-control px-3 text-sm md:min-h-9 max-md:min-h-11',
                  touchTarget,
                  isActive
                    ? 'bg-accent font-medium text-foreground'
                    : 'text-muted-foreground hover:bg-accent',
                )
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
