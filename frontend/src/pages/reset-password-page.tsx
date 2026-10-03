import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiRequest } from '@/api/request'
import { csrf, sessionQueryKey, type Session } from '@/api/auth'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import { ErrorState, LoadingState } from '@/components/states/async-states'

export function ResetPasswordPage() {
  const { token = '' } = useParams()
  const preview = useQuery({
    queryKey: ['password-reset-preview', token],
    queryFn: async () => {
      await csrf()
      return apiRequest<{ status: string }>('password-resets/preview/', {
        token,
      })
    },
    retry: false,
    enabled: Boolean(token),
  })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const cache = useQueryClient()
  const redeem = useMutation({
    mutationFn: async () => {
      await csrf()
      return apiRequest<Session>('password-resets/redeem/', { token, password })
    },
    onSuccess: (data) => {
      cache.setQueryData(sessionQueryKey, data)
      navigate('/inbox', { replace: true })
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setError('')
    redeem.mutate()
  }
  return (
    <AuthLayout>
      <h1 className="mb-5 text-xl font-semibold">Reset password</h1>
      {preview.isPending ? (
        <LoadingState label="Checking reset link" />
      ) : preview.isError ? (
        <ErrorState
          title="Could not check this reset link"
          description="Retry the check. If the link has expired, ask an owner for a new one."
          onRetry={() => void preview.refetch()}
          isRetrying={preview.isFetching}
        />
      ) : preview.data.status !== 'valid' ? (
        <div className="grid gap-2">
          <p role="status">
            This reset link has expired or is no longer available.
          </p>
          <p className="text-sm text-muted-foreground">
            Ask a workspace owner for a new reset link.
          </p>
          <Link className="w-fit underline" to="/sign-in">
            Sign in
          </Link>
        </div>
      ) : (
        <form className="grid gap-4" onSubmit={submit}>
          <Field
            id="password"
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={
              error ||
              (
                redeem.error as {
                  fieldErrors?: Record<string, string[]>
                } | null
              )?.fieldErrors?.password?.[0]
            }
          />
          <Field
            id="confirm"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
          {redeem.isError ? <p role="alert">{redeem.error.message}</p> : null}
          <Button type="submit" disabled={redeem.isPending}>
            Save password
          </Button>
        </form>
      )}
    </AuthLayout>
  )
}
