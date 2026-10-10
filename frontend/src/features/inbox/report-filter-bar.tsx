import { useState, type FormEvent, type ReactNode } from 'react'
import { Search, SlidersHorizontal, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import type { InboxQuery } from '@/api/reports'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { RetryButton } from '@/components/states/async-states'
import { cn } from '@/lib/utils'
import {
  hasActiveFilters,
  hiddenFilterCount,
  sourceKinds,
  UNASSIGNED,
  withFilters,
  withoutFilters,
  type FilterKey,
} from './inbox-query'
import { memberName } from './report-format'
import { StatusChips } from './status-chips'
import { useMembers } from './use-members'

const FILTERS_ID = 'inbox-filters'

export function ReportFilterBar({
  workspaceId,
  query,
  open,
  onOpenChange,
}: {
  workspaceId: string
  query: InboxQuery
  /** Phone width only: whether the filters behind the Filters button show. */
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(query.q ?? '')
  const [customer, setCustomer] = useState(query.customer ?? '')
  const members = useMembers(workspaceId)
  const selectedAssigneeKnown =
    !query.assignee ||
    query.assignee === UNASSIGNED ||
    members.data?.some((member) => member.id === query.assignee)
  const hiddenCount = hiddenFilterCount(query)
  // Below md these stay out of the first screen until the member asks.
  const collapsed = !open && 'max-md:hidden'

  function apply(changes: Partial<Record<FilterKey, string>>) {
    setParams(withFilters(params, changes))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    apply({ q: text, customer })
  }

  return (
    <section aria-label="Search and filter reports" className="grid gap-3">
      <form
        role="search"
        className="flex flex-wrap items-center gap-2"
        onSubmit={submit}
      >
        <div className="relative min-w-0 flex-1 basis-40">
          <Label htmlFor="inbox-search" className="sr-only">
            Search reports
          </Label>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            id="inbox-search"
            type="search"
            placeholder="Search reports"
            value={text}
            maxLength={200}
            className="pl-8"
            onChange={(event) => setText(event.target.value)}
          />
        </div>
        <div
          className={cn(
            'min-w-0 max-md:order-last max-md:basis-full md:w-56',
            collapsed,
          )}
        >
          <Label htmlFor="inbox-customer" className="sr-only">
            Customer
          </Label>
          <Input
            id="inbox-customer"
            type="search"
            placeholder="Customer"
            value={customer}
            maxLength={200}
            onChange={(event) => setCustomer(event.target.value)}
          />
        </div>
        <Button type="submit" className="h-10">
          <Search aria-hidden="true" />
          <span className="max-md:sr-only">Search</span>
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-10 md:hidden"
          aria-expanded={open}
          aria-controls={FILTERS_ID}
          onClick={() => onOpenChange(!open)}
        >
          <SlidersHorizontal aria-hidden="true" />
          Filters
          {hiddenCount ? (
            <span className="font-mono text-xs text-muted-foreground">
              <span aria-hidden="true">{hiddenCount}</span>
              <span className="sr-only">, {hiddenCount} active</span>
            </span>
          ) : null}
        </Button>
      </form>
      <div
        id={FILTERS_ID}
        className={cn('flex flex-wrap items-center gap-2', collapsed)}
      >
        <StatusChips
          workspaceId={workspaceId}
          query={query}
          onChange={(triageState) => apply({ triage_state: triageState })}
        />
        <div className="flex min-w-0 gap-2 max-md:w-full">
          <CompactSelect
            id="inbox-assignee"
            label="Assignee"
            value={query.assignee ?? ''}
            onChange={(value) => apply({ assignee: value })}
          >
            <option value="">Any assignee</option>
            <option value={UNASSIGNED}>Unassigned</option>
            {members.data?.map((member) => (
              <option key={member.id} value={member.id}>
                {memberName(member)}
              </option>
            ))}
            {!selectedAssigneeKnown ? (
              <option value={query.assignee}>Selected member</option>
            ) : null}
          </CompactSelect>
          <CompactSelect
            id="inbox-source"
            label="Source"
            value={query.source_kind ?? ''}
            onChange={(value) => apply({ source_kind: value })}
          >
            <option value="">All sources</option>
            {sourceKinds.map((kind) => (
              <option key={kind.value} value={kind.value}>
                {kind.label}
              </option>
            ))}
          </CompactSelect>
        </div>
        {hasActiveFilters(query) ? (
          <Button
            variant="ghost"
            onClick={() => setParams(withoutFilters(params))}
          >
            <X aria-hidden="true" />
            Clear filters
          </Button>
        ) : null}
      </div>
      {members.isError ? (
        <div className="flex flex-wrap items-center gap-2">
          <p role="status" className="text-sm text-muted-foreground">
            Member names could not be refreshed.
          </p>
          <RetryButton
            onRetry={() => void members.refetch()}
            isRetrying={members.isFetching}
          />
        </div>
      ) : null}
    </section>
  )
}

/** A select whose empty option names the filter, so its label can be hidden. */
function CompactSelect({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  children: ReactNode
}) {
  return (
    <div className="min-w-0 flex-1 md:w-40 md:flex-none">
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <NativeSelect
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </NativeSelect>
    </div>
  )
}
