import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { listMembers, reportKeys, type ReportQuery } from '@/api/reports'
import { Field, SelectField } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import {
  hasActiveFilters,
  sourceKinds,
  triageStates,
  UNASSIGNED,
  withFilters,
  withoutFilters,
  type FilterKey,
} from './inbox-query'
import { memberName } from './report-format'

export function ReportFilterBar({
  workspaceId,
  query,
}: {
  workspaceId: string
  query: ReportQuery
}) {
  const [params, setParams] = useSearchParams()
  const [text, setText] = useState(query.q ?? '')
  const [customer, setCustomer] = useState(query.customer ?? '')
  const members = useQuery({
    queryKey: reportKeys.members(workspaceId),
    queryFn: () => listMembers(workspaceId),
    staleTime: 60_000,
  })
  const selectedAssigneeKnown =
    !query.assignee ||
    query.assignee === UNASSIGNED ||
    members.data?.some((member) => member.id === query.assignee)

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
        className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end"
        onSubmit={submit}
      >
        <Field
          id="inbox-search"
          label="Search reports"
          type="search"
          placeholder="Title, description, or message"
          value={text}
          maxLength={200}
          onChange={(event) => setText(event.target.value)}
        />
        <Field
          id="inbox-customer"
          label="Customer"
          type="search"
          placeholder="Organisation or contact reference"
          value={customer}
          maxLength={200}
          onChange={(event) => setCustomer(event.target.value)}
        />
        <Button type="submit" size="lg" className="h-10">
          <Search aria-hidden="true" />
          Search
        </Button>
      </form>
      <div className="grid gap-3 sm:grid-cols-3">
        <SelectField
          id="inbox-state"
          label="Status"
          value={query.triage_state ?? ''}
          onChange={(event) => apply({ triage_state: event.target.value })}
        >
          <option value="">All statuses</option>
          {triageStates.map((state) => (
            <option key={state.value} value={state.value}>
              {state.label}
            </option>
          ))}
        </SelectField>
        <SelectField
          id="inbox-assignee"
          label="Assignee"
          value={query.assignee ?? ''}
          onChange={(event) => apply({ assignee: event.target.value })}
          hint={
            members.isError ? 'The member list could not be loaded.' : undefined
          }
        >
          <option value="">Anyone</option>
          <option value={UNASSIGNED}>Unassigned</option>
          {members.data?.map((member) => (
            <option key={member.id} value={member.id}>
              {memberName(member)}
            </option>
          ))}
          {!selectedAssigneeKnown ? (
            <option value={query.assignee}>Selected member</option>
          ) : null}
        </SelectField>
        <SelectField
          id="inbox-source"
          label="Source"
          value={query.source_kind ?? ''}
          onChange={(event) => apply({ source_kind: event.target.value })}
        >
          <option value="">All sources</option>
          {sourceKinds.map((kind) => (
            <option key={kind.value} value={kind.value}>
              {kind.label}
            </option>
          ))}
        </SelectField>
      </div>
      {hasActiveFilters(query) ? (
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setParams(withoutFilters(params))}
          >
            <X aria-hidden="true" />
            Clear filters
          </Button>
        </div>
      ) : null}
    </section>
  )
}
