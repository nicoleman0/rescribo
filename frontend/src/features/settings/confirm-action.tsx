import { useId, useRef, useState } from 'react'
import { ConfirmPanel } from '@/components/confirm/confirm-panel'
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
    <ConfirmPanel
      title={label}
      description={scope}
      confirmLabel={label}
      pendingLabel="Working…"
      isPending={action.isPending}
      confirmDisabled={confirmation !== phrase}
      onConfirm={() => {
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
      onCancel={() => {
        setOpen(false)
        setConfirmation('')
        action.reset()
        requestAnimationFrame(() => triggerRef.current?.focus())
      }}
    >
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
    </ConfirmPanel>
  )
}
