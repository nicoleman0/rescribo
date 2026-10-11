import { useState, type CSSProperties, type ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { CircleDot, Inbox, MessageSquareText, Settings } from 'lucide-react'
import {
  Link,
  NavLink,
  Outlet,
  matchPath,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { logout, getSession, sessionQueryKey } from '@/api/auth'
import { useOptionalWorkspace } from '@/components/auth/use-workspace'
import { Wordmark } from '@/components/brand/wordmark'
import { Badge } from '@/components/ui/badge'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { Breadcrumbs } from './breadcrumbs'
import { readSidebarOpen, writeSidebarOpen } from './sidebar-state'
import { useNavigationCounts } from './use-navigation-counts'
import { UserMenu } from './user-menu'
import { cn } from '@/lib/utils'

type NavigationItem = {
  label: string
  path: string
  icon: LucideIcon
  count?: number
  countLabel?: string
}

function Navigation({
  mobile = false,
  counts,
}: {
  mobile?: boolean
  counts: ReturnType<typeof useNavigationCounts>
}) {
  const items: NavigationItem[] = [
    {
      label: 'Inbox',
      path: '/inbox',
      icon: Inbox,
      count: counts.reports,
      countLabel: 'new reports',
    },
    { label: 'Problems', path: '/problems', icon: CircleDot },
    {
      label: 'Follow-ups',
      path: '/follow-ups',
      icon: MessageSquareText,
      count: counts.followUps,
      countLabel: 'follow-ups need approval',
    },
    { label: 'Settings', path: '/settings', icon: Settings },
  ]
  const { pathname } = useLocation()
  if (mobile)
    return (
      <nav
        aria-label="Primary navigation"
        className="flex h-16 items-stretch border-t border-border bg-card px-1"
      >
        {items.map(({ label, path, icon: Icon, count, countLabel }) => (
          <NavLink
            key={path}
            to={path}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                'relative flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-control px-1 text-[11px] text-muted-foreground hover:bg-selected hover:text-foreground',
                isActive && 'bg-selected font-medium text-foreground',
              )
            }
          >
            <Icon aria-hidden="true" className="size-4 shrink-0" />
            <span className="truncate">{label}</span>
            {count !== undefined && count > 0 ? (
              <span className="absolute right-1/2 top-1 -translate-x-[-1.8rem] rounded-full bg-primary px-1.5 text-[10px] leading-4 text-primary-foreground">
                <span className="sr-only">{`${count} ${countLabel}`}</span>
                {count > 99 ? '99+' : count}
              </span>
            ) : null}
          </NavLink>
        ))}
      </nav>
    )
  return (
    <nav aria-label="Primary navigation">
      <SidebarMenu>
        {items.map(({ label, path, icon: Icon, count, countLabel }) => (
          <SidebarMenuItem key={path} className="relative">
            <SidebarMenuButton
              asChild
              isActive={Boolean(matchPath({ path, end: false }, pathname))}
              tooltip={label}
              className="h-11 min-h-11 rounded-control px-3 text-sm group-data-[collapsible=icon]:size-11! group-data-[collapsible=icon]:p-0"
            >
              <NavLink to={path} aria-label={label}>
                <Icon aria-hidden="true" className="size-4 shrink-0" />
                <span className="group-data-[collapsible=icon]:hidden">
                  {label}
                </span>
              </NavLink>
            </SidebarMenuButton>
            {count !== undefined && count > 0 ? (
              <SidebarMenuBadge className="right-2 font-mono group-data-[collapsible=icon]:!flex group-data-[collapsible=icon]:right-0 group-data-[collapsible=icon]:top-0 group-data-[collapsible=icon]:translate-x-1/3">
                <span className="sr-only">{`${count} ${countLabel}`}</span>
                {count > 99 ? '99+' : count}
              </SidebarMenuBadge>
            ) : null}
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </nav>
  )
}

function ShellContents({
  children,
  isGallery,
  isDemo,
  workspaceName,
  session,
  counts,
  signOut,
  signOutPending,
  signOutError,
}: {
  children?: ReactNode
  isGallery: boolean
  isDemo: boolean
  workspaceName: string
  session?: Awaited<ReturnType<typeof getSession>>
  counts: ReturnType<typeof useNavigationCounts>
  signOut: () => void
  signOutPending: boolean
  signOutError?: string
}) {
  const { open, isMobile } = useSidebar()
  return (
    <>
      {/* First in the document so it is the first Tab stop. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-control focus:bg-background focus:px-4 focus:py-3 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        Skip to main content
      </a>
      {!isGallery && !isMobile ? (
        <Sidebar
          aria-label="Application sidebar"
          collapsible="icon"
          role="complementary"
          className="border-border"
        >
          <SidebarHeader className="h-16 justify-center border-b border-border px-3">
            {open ? (
              <Link
                to="/inbox"
                aria-label="rescribo, go to inbox"
                className="rounded-control focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <Wordmark />
              </Link>
            ) : null}
          </SidebarHeader>
          <SidebarContent className="px-3 py-3">
            <SidebarGroup className="p-0">
              <SidebarGroupContent>
                <Navigation counts={counts} />
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          {!isGallery && session ? (
            <SidebarFooter className="border-t border-border p-2">
              <UserMenu
                session={session}
                workspaceName={workspaceName}
                isDemo={isDemo}
                collapsed={!open}
                onSignOut={signOut}
                signOutPending={signOutPending}
              />
            </SidebarFooter>
          ) : null}
        </Sidebar>
      ) : null}
      <div className="flex min-h-svh min-w-0 flex-1 flex-col pb-16 md:pb-0">
        <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-background px-4 md:px-8">
          <div className="flex min-w-0 items-center gap-3">
            {!isGallery ? (
              <SidebarTrigger className="hidden size-11 md:flex" />
            ) : null}
            <div className="min-w-0">
              <Breadcrumbs />
            </div>
            {isDemo ? (
              <Badge
                variant="secondary"
                aria-label="Demo workspace"
                className="shrink-0"
              >
                Demo
              </Badge>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {/* The command palette trigger belongs in this header group. */}
            {signOutError ? (
              <p role="alert" className="max-w-48 text-xs text-destructive">
                {signOutError}
              </p>
            ) : null}
            {!isGallery && session ? (
              <UserMenu
                phone
                session={session}
                workspaceName={workspaceName}
                isDemo={isDemo}
                onSignOut={signOut}
                signOutPending={signOutPending}
              />
            ) : null}
          </div>
        </header>
        <SidebarInset
          id="main-content"
          tabIndex={-1}
          className="min-w-0 flex-1 px-4 py-6 outline-none focus-visible:ring-2 focus-visible:ring-ring md:px-8 md:py-8"
        >
          <div className="mx-auto w-full max-w-5xl">
            {children ?? <Outlet />}
          </div>
        </SidebarInset>
        {!isGallery ? (
          <div className="fixed inset-x-0 bottom-0 z-10 md:hidden">
            <Navigation mobile counts={counts} />
          </div>
        ) : null}
      </div>
    </>
  )
}

export function AppShell({ children }: { children?: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(readSidebarOpen)
  const location = useLocation()
  const isGallery = location.pathname === '/dev/ui'
  const workspace = useOptionalWorkspace()
  const workspaceId = workspace?.workspace.id
  const isDemo = !isGallery && workspace?.workspace.is_demo === true
  const sessionQuery = useQuery({
    queryKey: sessionQueryKey,
    queryFn: getSession,
    enabled: !isGallery,
    retry: false,
  })
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const signOut = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: sessionQueryKey })
      navigate('/sign-in', { replace: true })
    },
  })
  const counts = useNavigationCounts(workspaceId)
  return (
    <TooltipProvider>
      <SidebarProvider
        open={sidebarOpen}
        style={
          {
            '--sidebar-width': '14rem',
            '--sidebar-width-icon': '4.25rem',
          } as CSSProperties
        }
        onOpenChange={(open) => {
          writeSidebarOpen(open)
          setSidebarOpen(open)
        }}
      >
        <ShellContents
          isGallery={isGallery}
          isDemo={isDemo}
          workspaceName={workspace?.workspace.name ?? 'Workspace'}
          session={sessionQuery.data}
          counts={counts}
          signOut={() => signOut.mutate()}
          signOutPending={signOut.isPending}
          signOutError={signOut.isError ? signOut.error.message : undefined}
        >
          {children}
        </ShellContents>
      </SidebarProvider>
    </TooltipProvider>
  )
}
