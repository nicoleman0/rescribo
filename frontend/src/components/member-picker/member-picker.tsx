import { useState, type ReactNode } from 'react'
import { ChevronsUpDownIcon } from 'lucide-react'
import type { MemberDirectoryEntry, MemberSummary } from '@/api/reports'
import type { ApiError } from '@/api/request'
import { fieldError } from '@/components/forms/field-error'
import { ActionError } from '@/components/states/action-error'
import { ErrorState } from '@/components/states/async-states'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

/** The part of a members query the picker reads. */
export type MembersSource = {
  data?: MemberDirectoryEntry[]
  isPending: boolean
  isError: boolean
  isFetching: boolean
  refetch: () => unknown
}

// Match on the name only, not the id that cmdk uses as the item value.
const matchName = (_value: string, search: string, keywords?: string[]) =>
  keywords?.some((word) => word.toLowerCase().includes(search.toLowerCase()))
    ? 1
    : 0

/** Choose a member for a saved field. A choice saves at once through
 * `onChoose`; there is no save button. A resolved save closes the picker. A
 * rejected one keeps it open so the caller's `error` shows beside the list. */
export function MemberPicker({
  label,
  value,
  current,
  members,
  emptyLabel,
  unavailableLabel = 'Unavailable',
  isUnavailable,
  note,
  error,
  pending,
  triggerVariant = 'outline',
  triggerClassName,
  onChoose,
  onClose,
}: {
  /** Names the field. The trigger's accessible name adds the current member. */
  label: string
  /** The member id shown now, or '' for none. */
  value: string
  /** The record's member, listed even when absent from `members`. */
  current: MemberSummary | null
  members: MembersSource
  /** Choice that clears the field. Leave out when the field is required. */
  emptyLabel?: string
  unavailableLabel?: string
  isUnavailable?: (member: MemberDirectoryEntry) => boolean
  /** Shown at the top of the open picker, before any choice. */
  note?: ReactNode
  error?: ReactNode
  pending: boolean
  triggerVariant?: 'outline' | 'ghost'
  triggerClassName?: string
  onChoose: (memberId: string) => Promise<unknown>
  onClose?: () => void
}) {
  const [open, setOpen] = useState(false)
  const listed = members.data ?? []
  const currentIsListed = !current || listed.some((m) => m.id === current.id)
  const shown =
    listed.find((member) => member.id === value)?.display_name ??
    (current?.id === value ? current.display_name : undefined)
  const triggerText = value ? (shown ?? '') : (emptyLabel ?? '')

  function changeOpen(next: boolean) {
    // A save in flight owns the picker until it settles.
    if (!next && pending) return
    setOpen(next)
    if (!next) onClose?.()
  }

  async function choose(memberId: string) {
    if (pending) return
    if (memberId === value) return changeOpen(false)
    try {
      await onChoose(memberId)
    } catch {
      // The caller renders the failure from its mutation state.
      return
    }
    setOpen(false)
    onClose?.()
  }

  return (
    <Popover open={open} onOpenChange={changeOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant={triggerVariant}
          role="combobox"
          aria-expanded={open}
          aria-label={`${label}: ${triggerText || 'none'}`}
          className={cn(
            'min-w-0 justify-between gap-2',
            triggerVariant === 'ghost' && '-ml-2.5 max-w-full',
            triggerClassName,
          )}
        >
          <span
            className={cn(
              'min-w-0 truncate',
              !value && 'text-muted-foreground',
            )}
          >
            {triggerText}
          </span>
          <ChevronsUpDownIcon
            aria-hidden="true"
            className="size-3.5 text-muted-foreground"
          />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="grid gap-1 p-1">
        {note ? (
          <p className="px-2 pt-1.5 text-xs text-muted-foreground">{note}</p>
        ) : null}
        <Command filter={matchName} label={`Search ${label}`}>
          <CommandInput placeholder="Search members" />
          <CommandList>
            {members.isPending ? (
              <p
                role="status"
                className="px-2 py-3 text-sm text-muted-foreground"
              >
                Loading members…
              </p>
            ) : null}
            <CommandEmpty>No members match.</CommandEmpty>
            <CommandGroup>
              {emptyLabel ? (
                <CommandItem
                  value="__none__"
                  keywords={[emptyLabel]}
                  disabled={pending}
                  data-checked={value === ''}
                  onSelect={() => void choose('')}
                >
                  {emptyLabel}
                </CommandItem>
              ) : null}
              {listed.map((member) => (
                <CommandItem
                  key={member.id}
                  value={member.id}
                  keywords={[member.display_name]}
                  disabled={
                    pending ||
                    (isUnavailable?.(member) === true && member.id !== value)
                  }
                  data-checked={member.id === value}
                  onSelect={() => void choose(member.id)}
                >
                  {member.display_name}
                  {isUnavailable?.(member) ? (
                    <>
                      {' '}
                      <span className="text-xs text-muted-foreground">
                        ({unavailableLabel})
                      </span>
                    </>
                  ) : null}
                </CommandItem>
              ))}
              {currentIsListed || !current ? null : (
                <CommandItem
                  value={current.id}
                  keywords={[current.display_name]}
                  disabled={pending}
                  data-checked={current.id === value}
                  onSelect={() => void choose(current.id)}
                >
                  {current.display_name}
                </CommandItem>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
        {pending ? (
          <p role="status" className="px-2 pb-1 text-xs text-muted-foreground">
            Saving…
          </p>
        ) : null}
        {members.isError ? (
          <ErrorState
            title="Could not load members"
            description="Retry to update the choices."
            onRetry={() => void members.refetch()}
            isRetrying={members.isFetching}
          />
        ) : null}
        {error}
      </PopoverContent>
    </Popover>
  )
}

/** A failed save inside the picker: the field's own error, then the action
 * failure. The field error is read first so the summary does not repeat it. */
export function MemberPickerError({
  error,
  field,
  title,
  record,
}: {
  error: ApiError | null
  field: string
  title: string
  record: 'report' | 'problem'
}) {
  if (!error) return null
  const message = fieldError(error, field)
  return (
    <>
      {message ? (
        <p role="alert" className="px-2 text-sm text-destructive">
          {message}
        </p>
      ) : null}
      <ActionError error={error} title={title} record={record} />
    </>
  )
}
