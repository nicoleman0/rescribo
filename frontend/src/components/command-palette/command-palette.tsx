import { useLayoutEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { NAVIGATION_ITEMS } from '@/components/layout/navigation-items'
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from '@/components/ui/command'
import { useIsMobile } from '@/hooks/use-mobile'
import { boundShortcuts, runShortcut, shortcutKeys } from '@/lib/shortcuts'
import { THEMES, useThemePreference, type ThemePreference } from '@/lib/theme'
import { usePaletteSearch } from './use-palette-search'

const SCREENS = [
  ...NAVIGATION_ITEMS.map(({ label, path }) => ({ label, path })),
  { label: 'New report', path: '/inbox/new' },
]

const THEME_CHOICES: { value: ThemePreference; label: string }[] = [
  ...THEMES,
  'system' as const,
].map((value) => ({
  value,
  label: `${value[0].toUpperCase()}${value.slice(1)} theme`,
}))

const matches = (label: string, text: string) =>
  label.toLowerCase().includes(text.toLowerCase())

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: string
}

export function CommandPalette({ open, onOpenChange, workspaceId }: Props) {
  const [text, setText] = useState('')
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  const [preference, setPreference] = useThemePreference()
  const search = usePaletteSearch(workspaceId, text, open)
  const term = text.trim()
  // The palette opens from a key or the trigger; Radix restores focus only to
  // its own trigger, so remember where focus was.
  const returnFocusTo = useRef<Element | null>(null)
  useLayoutEffect(() => {
    if (open) returnFocusTo.current = document.activeElement
  }, [open])

  const changeOpen = (next: boolean) => {
    if (!next) setText('')
    onOpenChange(next)
  }
  const go = (path: string) => {
    navigate(path)
    changeOpen(false)
  }

  const screens = SCREENS.filter(({ label }) => matches(label, term))
  const themes = THEME_CHOICES.filter(({ label }) => matches(label, term))
  const shortcuts = isMobile
    ? []
    : boundShortcuts().filter(({ label }) => matches(label, term))

  return (
    <CommandDialog
      open={open}
      onOpenChange={changeOpen}
      title="Command palette"
      onCloseAutoFocus={(event) => {
        event.preventDefault()
        if (returnFocusTo.current instanceof HTMLElement)
          returnFocusTo.current.focus()
      }}
      description="Go to a screen, find a report or problem, change the theme, or see keyboard shortcuts."
    >
      <Command shouldFilter={false} label="Command palette">
        <CommandInput
          value={text}
          onValueChange={setText}
          placeholder="Search screens, reports, and problems"
        />
        <CommandList>
          <CommandEmpty>No results</CommandEmpty>
          {screens.length > 0 ? (
            <CommandGroup heading="Go to">
              {screens.map(({ label, path }) => (
                <CommandItem
                  key={path}
                  value={`go-${path}`}
                  onSelect={() => go(path)}
                >
                  {label}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          {search.active ? (
            <>
              <SearchGroup
                heading="Reports"
                state={search.reports}
                render={(report) => (
                  <CommandItem
                    key={report.id}
                    value={`report-${report.id}`}
                    onSelect={() => go(`/inbox/${report.id}`)}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {report.title}
                    </span>
                    {report.customer_label ? (
                      <span className="max-w-[40%] truncate text-xs text-muted-foreground">
                        {report.customer_label}
                      </span>
                    ) : null}
                  </CommandItem>
                )}
              />
              <SearchGroup
                heading="Problems"
                state={search.problems}
                render={(problem) => (
                  <CommandItem
                    key={problem.id}
                    value={`problem-${problem.id}`}
                    onSelect={() => go(`/problems/${problem.id}`)}
                  >
                    <span className="min-w-0 flex-1 truncate">
                      {problem.title}
                    </span>
                  </CommandItem>
                )}
              />
            </>
          ) : null}
          {themes.length > 0 ? (
            <CommandGroup heading="Theme">
              {themes.map(({ value, label }) => (
                <CommandItem
                  key={value}
                  value={`theme-${value}`}
                  data-checked={preference === value}
                  onSelect={() => {
                    setPreference(value)
                    changeOpen(false)
                  }}
                >
                  {label}
                  {preference === value ? (
                    <span className="sr-only">, current</span>
                  ) : null}
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
          {shortcuts.length > 0 ? (
            <CommandGroup heading="Shortcuts">
              {shortcuts.map(({ id, label }) => (
                <CommandItem
                  key={id}
                  value={`shortcut-${id}`}
                  onSelect={() => {
                    runShortcut(id)
                    changeOpen(false)
                  }}
                >
                  {label}{' '}
                  <CommandShortcut>
                    {shortcutKeys(id).join(' ')}
                  </CommandShortcut>
                </CommandItem>
              ))}
            </CommandGroup>
          ) : null}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}

type SearchState<T> = {
  rows: T[]
  searching: boolean
  failed: boolean
  retry: () => void
}

function SearchGroup<T>({
  heading,
  state,
  render,
}: {
  heading: string
  state: SearchState<T>
  render: (row: T) => React.ReactNode
}) {
  if (state.searching)
    return (
      <CommandGroup heading={heading}>
        <CommandItem value={`${heading}-searching`} disabled>
          Searching…
        </CommandItem>
      </CommandGroup>
    )
  if (state.failed)
    return (
      <CommandGroup heading={heading}>
        <CommandItem value={`${heading}-retry`} onSelect={state.retry}>
          {heading} could not be searched. Retry
        </CommandItem>
      </CommandGroup>
    )
  if (state.rows.length === 0) return null
  return <CommandGroup heading={heading}>{state.rows.map(render)}</CommandGroup>
}
