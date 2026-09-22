import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { CircleDot, Inbox, MessageSquareText, Settings } from 'lucide-react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { logout, sessionQueryKey } from '@/api/auth'
import { useOptionalWorkspace } from '@/components/auth/use-workspace'
import { Button } from '@/components/ui/button'

type NavigationItem = {
  label: string
  path: string
  icon: LucideIcon
}

const navigationItems: NavigationItem[] = [
  { label: 'Inbox', path: '/inbox', icon: Inbox },
  { label: 'Problems', path: '/problems', icon: CircleDot },
  { label: 'Follow-ups', path: '/follow-ups', icon: MessageSquareText },
  { label: 'Settings', path: '/settings', icon: Settings },
]

function Navigation({ mobile = false }: { mobile?: boolean }) {
  return (
    <nav
      aria-label="Primary navigation"
      className={cn(
        mobile
          ? 'flex h-16 items-stretch border-t border-border bg-card px-1'
          : 'flex flex-col gap-1',
      )}
    >
      {navigationItems.map(({ label, path, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) =>
            cn(
              'group flex items-center gap-3 text-muted-foreground transition-colors hover:bg-selected hover:text-foreground',
              mobile
                ? 'min-w-0 flex-1 flex-col justify-center gap-1 rounded-control px-1 text-[11px]'
                : 'min-h-11 rounded-control px-3 text-sm',
              isActive && 'bg-selected font-medium text-foreground',
            )
          }
        >
          <Icon aria-hidden="true" className="size-4 shrink-0" />
          <span className={cn(mobile && 'truncate')}>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export function AppShell({ children }: { children?: ReactNode }) {
  const location = useLocation()
  const isGallery = location.pathname === '/dev/ui'
  const workspace = useOptionalWorkspace()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: sessionQueryKey })
      navigate('/sign-in', { replace: true })
    },
  })

  return (
    <div className="min-h-svh bg-background md:grid md:grid-cols-[14rem_minmax(0,1fr)]">
      <aside className="hidden border-r border-border bg-sidebar md:flex md:flex-col">
        <div className="flex h-16 items-center border-b border-border px-5">
          <span className="text-base font-semibold tracking-[-0.02em]">
            Rescribo
          </span>
        </div>
        <div className="flex flex-1 flex-col p-3">
          <Navigation />
          <div className="mt-auto border-t border-border pt-3">
            <Button
              className="w-full"
              variant="outline"
              size="sm"
              onClick={() => signOut.mutate()}
              disabled={signOut.isPending}
            >
              Sign out
            </Button>
          </div>
        </div>
      </aside>

      <div className="flex min-h-svh min-w-0 flex-col pb-16 md:pb-0">
        <header className="flex h-16 items-center justify-between border-b border-border bg-background px-4 md:px-8">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {isGallery
                ? 'UI gallery'
                : (workspace?.workspace.name ?? 'Workspace')}
            </p>
            <p className="hidden text-xs text-muted-foreground sm:block">
              Quiet surfaces for focused triage
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
              Updated just now
            </span>
            {!isGallery ? (
              <Button
                className="md:hidden"
                size="sm"
                variant="outline"
                onClick={() => signOut.mutate()}
                disabled={signOut.isPending}
              >
                Sign out
              </Button>
            ) : null}
          </div>
        </header>

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto w-full max-w-5xl">
            {children ?? <Outlet />}
          </div>
        </main>
      </div>

      {!isGallery ? (
        <div className="fixed inset-x-0 bottom-0 z-10 md:hidden">
          <Navigation mobile />
        </div>
      ) : null}
    </div>
  )
}
