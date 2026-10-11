import { useEffect, useRef, type FormEvent, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

export function ConfirmPanel({
  title,
  description,
  confirmLabel,
  pendingLabel,
  isPending,
  confirmDisabled = false,
  headingLevel = 3,
  focusOnOpen = false,
  onConfirm,
  onCancel,
  children,
}: {
  title: string
  description: string
  confirmLabel: string
  pendingLabel: string
  isPending: boolean
  confirmDisabled?: boolean
  headingLevel?: 3 | 4
  focusOnOpen?: boolean
  onConfirm: () => void
  onCancel: () => void
  children?: ReactNode
}) {
  const titleRef = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    if (focusOnOpen) titleRef.current?.focus()
  }, [focusOnOpen])

  const Heading = headingLevel === 3 ? 'h3' : 'h4'
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onConfirm()
  }

  return (
    <form
      className="grid gap-3 rounded-control border border-destructive p-4"
      aria-label={title}
      onSubmit={submit}
    >
      <Heading
        ref={titleRef}
        className="font-semibold"
        tabIndex={focusOnOpen ? -1 : undefined}
      >
        {title}
      </Heading>
      <p className="max-w-prose text-sm">{description}</p>
      {children}
      <div className="flex flex-wrap gap-2">
        <Button
          variant="destructive"
          className="h-auto min-h-11 max-w-full py-2 text-left break-words whitespace-normal"
          disabled={confirmDisabled || isPending}
        >
          {isPending ? pendingLabel : confirmLabel}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          disabled={isPending}
          onClick={onCancel}
        >
          Cancel
        </Button>
      </div>
    </form>
  )
}
