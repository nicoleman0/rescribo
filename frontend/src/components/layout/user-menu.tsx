import { useState } from 'react'
import { ChevronUp, LogOut } from 'lucide-react'
import type { Session } from '@/api/auth'
import { demoDescription } from '@/components/auth/use-workspace'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { THEMES, useThemePreference, type ThemePreference } from '@/lib/theme'
import { cn } from '@/lib/utils'

type Props = {
  session: Session
  workspaceName: string
  isDemo: boolean
  collapsed?: boolean
  phone?: boolean
  onSignOut: () => void
  signOutPending?: boolean
}

export function UserMenu({
  session,
  workspaceName,
  isDemo,
  collapsed = false,
  phone = false,
  onSignOut,
  signOutPending = false,
}: Props) {
  const [open, setOpen] = useState(false)
  const [preference, setPreference] = useThemePreference()
  const name = session.user.full_name
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
  return (
    <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          aria-label={`User menu for ${name}`}
          className={cn(
            'flex h-auto min-h-11 w-full justify-start gap-3 px-2 text-left',
            collapsed && 'justify-center px-0',
            phone && 'touchTarget size-11 w-11 md:hidden',
          )}
        >
          <Avatar className="size-8 shrink-0">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
          {!collapsed && !phone ? (
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{name}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {workspaceName}
              </span>
            </span>
          ) : null}
          {!collapsed && !phone ? (
            <ChevronUp aria-hidden="true" className="size-4" />
          ) : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align={phone ? 'end' : 'start'}
        side={phone ? 'bottom' : 'top'}
        className="w-64 shadow-elevation-3"
      >
        <DropdownMenuLabel className="whitespace-normal text-foreground">
          <span className="block truncate">{name}</span>
          <span className="block truncate font-normal text-foreground">
            {session.user.email}
          </span>
          {isDemo ? (
            <span className="mt-2 block font-normal text-foreground">
              {demoDescription}
            </span>
          ) : null}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-foreground">Theme</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          aria-label="Theme"
          value={preference}
          onValueChange={(value) => setPreference(value as ThemePreference)}
        >
          {[...THEMES, 'system'].map((theme) => (
            <DropdownMenuRadioItem
              key={theme}
              value={theme}
              className="text-foreground"
            >
              {theme[0].toUpperCase() + theme.slice(1)}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onSignOut} disabled={signOutPending}>
          <LogOut aria-hidden="true" className="size-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
