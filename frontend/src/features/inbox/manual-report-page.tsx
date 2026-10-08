import type { FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  createManualReport,
  reportKeys,
  type ManualReportInput,
} from '@/api/reports'
import type { ApiError } from '@/api/request'
import { useWorkspace } from '@/components/auth/use-workspace'
import { Field, TextareaField } from '@/components/forms/field'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useReportDraft, type ReportDraft } from './use-report-draft'

function failureMessage(error: ApiError) {
  if (error.status === undefined) {
    return 'Could not reach Rescribo. Check your connection and try again.'
  }
  if (error.reason === 'invalid_request') return 'Check the highlighted fields.'
  return error.message
}

export function ManualReportPage() {
  const { workspace } = useWorkspace()
  return <ManualReportForm key={workspace.id} workspace={workspace} />
}

function ManualReportForm({
  workspace,
}: {
  workspace: { id: string; name: string }
}) {
  const { draft, restored, update, clear, prepareSubmission } = useReportDraft(
    workspace.id,
  )
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const mutation = useMutation({
    mutationFn: (input: ManualReportInput) =>
      createManualReport(workspace.id, input),
    onSuccess: (report) => {
      clear()
      queryClient.setQueryData(
        reportKeys.detail(workspace.id, report.id),
        report,
      )
      void queryClient.invalidateQueries({
        queryKey: reportKeys.all(workspace.id),
      })
      navigate(`/inbox/${report.id}`)
    },
  })
  const error = mutation.error as ApiError | null
  const fieldError = (field: keyof ReportDraft) =>
    error?.fieldErrors?.[field]?.[0]

  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate(prepareSubmission())
  }

  const field = (name: keyof ReportDraft) => ({
    id: `report-${name.replaceAll('_', '-')}`,
    name,
    value: draft[name],
    error: fieldError(name),
    onChange: (event: { target: { value: string } }) =>
      update(name, event.target.value),
  })

  return (
    <div className="animate-page-enter grid max-w-2xl gap-6">
      <header>
        <h1 className="text-xl font-semibold">New report</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Record one customer's experience. The report will be visible to all
          members of {workspace.name}.
        </p>
      </header>
      {restored ? (
        <Alert>
          <AlertTitle>Restored your unsaved draft</AlertTitle>
          <AlertDescription className="grid gap-2">
            <span>Continue editing, or discard it to start again.</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => {
                clear()
                mutation.reset()
              }}
            >
              Discard draft
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
      <form className="grid gap-4" onSubmit={submit} noValidate>
        <fieldset disabled={mutation.isPending} className="grid gap-4">
          <Field
            {...field('title')}
            label="Title"
            required
            maxLength={200}
            autoComplete="off"
          />
          <TextareaField
            {...field('description')}
            label="Description"
            maxLength={10000}
            rows={5}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              {...field('customer_label')}
              label="Customer organisation"
              maxLength={200}
              autoComplete="off"
            />
            <Field
              {...field('customer_contact_reference')}
              label="Contact reference"
              hint="For example a CRM ID. Not used to contact the customer."
              maxLength={200}
              autoComplete="off"
            />
          </div>
          <Field
            {...field('affected_version')}
            label="Affected version"
            maxLength={100}
            autoComplete="off"
          />
        </fieldset>
        {mutation.isError && error ? (
          <Alert variant="destructive">
            <AlertTitle>Could not confirm report creation</AlertTitle>
            <AlertDescription>
              {failureMessage(error)} Your draft is kept on this page.
            </AlertDescription>
          </Alert>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Creating report…' : 'Create report'}
          </Button>
          <Button asChild variant="outline">
            <Link to="/inbox">Cancel</Link>
          </Button>
        </div>
      </form>
    </div>
  )
}
