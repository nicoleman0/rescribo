import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { CircleDot, Inbox, MessageSquareText, Settings } from 'lucide-react'
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { logout, sessionQueryKey } from '@/api/auth'
import {
  demoDescription,
  useOptionalWorkspace,
} from '@/components/auth/use-workspace'
import { Wordmark } from '@/components/brand/wordmark'
import { Badge } from '@/components/ui/badge'
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
  const isDemo = !isGallery && workspace?.workspace.is_demo === true
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
      {/* First in the document so it is the first Tab stop. Fixed on focus, so the sidebar does not shift. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-control focus:bg-background focus:px-4 focus:py-3 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>
      <aside className="hidden border-r border-border bg-sidebar md:flex md:flex-col">
        <div className="flex h-16 items-center border-b border-border px-5">
          <Link
            to="/inbox"
            aria-label="rescribo, go to inbox"
            className="rounded-control focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            <Wordmark />
          </Link>
        </div>
        <div className="flex flex-1 flex-col p-3">
          <Navigation />
        </div>
      </aside>

      <div className="flex min-h-svh min-w-0 flex-col pb-16 md:pb-0">
        <header className="flex h-16 items-center justify-between border-b border-border bg-background px-4 md:px-8">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-sm font-medium">
                {isGallery
                  ? 'UI gallery'
                  : (workspace?.workspace.name ?? 'Workspace')}
              </p>
              {isDemo ? (
                <Badge variant="secondary" aria-label="Demo workspace">
                  Demo
                </Badge>
              ) : null}
            </div>
            <p className="hidden text-xs text-muted-foreground sm:block">
              {isDemo ? demoDescription : 'Quiet surfaces for focused triage'}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {signOut.isError ? (
              <p role="alert" className="max-w-48 text-xs text-destructive">
                {signOut.error.message}
              </p>
            ) : null}
            {!isGallery ? (
              <Button
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

        <main
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 px-4 py-6 outline-none focus-visible:ring-2 focus-visible:ring-ring md:px-8 md:py-8"
        >
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
