import { useId, useRef, useState } from 'react'
import { Field } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { ErrorState } from '@/components/states/async-states'
import { useSettingsAction } from './use-settings-action'

export function ConfirmAction({
  workspaceId,
  path,
  body = {},
  label,
  scope,
  phrase,
  onSuccess,
}: {
  workspaceId: string
  path: string
  body?: Record<string, unknown>
  label: string
  scope: string
  phrase: string
  onSuccess?: () => void
}) {
  const id = useId()
  const [open, setOpen] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const action = useSettingsAction(workspaceId)
  if (!open)
    return (
      <Button
        ref={triggerRef}
        variant="outline"
        className="h-auto min-h-11 w-fit max-w-full py-2 text-left break-words whitespace-normal text-destructive"
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
    )
  return (
    <form
      className="grid gap-3 rounded-control border border-destructive p-4"
      aria-label={label}
      onSubmit={(event) => {
        event.preventDefault()
        action.mutate(
          { path, body: { ...body, confirmation } },
          {
            onSuccess: () => {
              setOpen(false)
              setConfirmation('')
              onSuccess?.()
            },
          },
        )
      }}
    >
      <h3 className="font-semibold">{label}</h3>
      <p className="max-w-prose text-sm">{scope}</p>
      <Field
        id={id}
        label={`Type ${phrase} to confirm`}
        value={confirmation}
        onChange={(event) => setConfirmation(event.target.value)}
        autoComplete="off"
        autoFocus
        error={fieldError(action.error, 'confirmation')}
      />
      {action.error ? (
        <ErrorState
          title="Action failed"
          description={<FormErrorMessage error={action.error} />}
        />
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="destructive"
          className="h-auto min-h-11 max-w-full py-2 text-left break-words whitespace-normal"
          disabled={confirmation !== phrase || action.isPending}
        >
          {action.isPending ? 'Working…' : label}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={action.isPending}
          onClick={() => {
            setOpen(false)
            setConfirmation('')
            action.reset()
            requestAnimationFrame(() => triggerRef.current?.focus())
          }}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
