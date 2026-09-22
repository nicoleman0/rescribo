import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import { csrf, login, sessionQueryKey, type Session } from '@/api/auth'
import type { ApiError } from '@/api/request'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

export function SignInPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const mutation = useMutation({
    mutationFn: async () => {
      await csrf()
      return login(email, password)
    },
    onSuccess: (session: Session) => {
      queryClient.setQueryData(sessionQueryKey, session)
      const from = (location.state as { from?: { pathname?: string } } | null)
        ?.from?.pathname
      navigate(from ?? '/inbox', { replace: true })
    },
  })
  function submit(event: FormEvent) {
    event.preventDefault()
    mutation.mutate()
  }
  const apiError = mutation.error as ApiError | null
  return (
    <AuthLayout>
      <h1 className="text-xl font-semibold">Sign in</h1>
      <p className="mt-1 mb-6 text-sm text-muted-foreground">
        Use your workspace account.
      </p>
      <form className="grid gap-4" onSubmit={submit}>
        <Field
          id="email"
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={apiError?.fieldErrors?.email?.[0]}
        />
        <Field
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={apiError?.fieldErrors?.password?.[0]}
        />
        {mutation.isError ? (
          <Alert variant="destructive">
            <AlertDescription>{apiError?.message}</AlertDescription>
          </Alert>
        ) : null}
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthLayout>
  )
}
