import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'

type FieldProps = { id: string; label: string; error?: string; hint?: string }

function describedBy({ id, error, hint }: FieldProps) {
  const ids = [hint ? `${id}-hint` : '', error ? `${id}-error` : '']
  return ids.filter(Boolean).join(' ') || undefined
}

function FieldShell({
  id,
  label,
  error,
  hint,
  children,
}: FieldProps & { children: ReactNode }) {
  return (
    <div className="grid content-start gap-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export function Field({
  id,
  label,
  error,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & FieldProps) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint}>
      <Input
        {...props}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy({ id, label, error, hint })}
      />
    </FieldShell>
  )
}

export function TextareaField({
  id,
  label,
  error,
  hint,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint}>
      <Textarea
        {...props}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy({ id, label, error, hint })}
      />
    </FieldShell>
  )
}

export function SelectField({
  id,
  label,
  error,
  hint,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & FieldProps) {
  return (
    <FieldShell id={id} label={label} error={error} hint={hint}>
      <NativeSelect
        {...props}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy({ id, label, error, hint })}
      >
        {children}
      </NativeSelect>
    </FieldShell>
  )
}
