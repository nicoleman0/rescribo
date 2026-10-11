import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  csrf,
  demoOfferQueryKey,
  getDemoOffer,
  login,
  sessionQueryKey,
  type Session,
} from '@/api/auth'
import type { ApiError } from '@/api/request'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Field } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

export function SignInPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const signInButton = useRef<HTMLButtonElement>(null)
  const demoOffer = useQuery({
    queryKey: demoOfferQueryKey,
    queryFn: getDemoOffer,
    retry: false,
  })
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
  const credentials = demoOffer.data
  return (
    <AuthLayout title="Sign in">
      <p className="-mt-4 mb-6 text-sm text-muted-foreground">
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
          error={fieldError(apiError, 'email')}
        />
        <Field
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldError(apiError, 'password')}
        />
        {apiError ? (
          <Alert variant="destructive">
            <AlertDescription>
              <FormErrorMessage error={apiError} />
            </AlertDescription>
          </Alert>
        ) : null}
        <Button
          ref={signInButton}
          type="submit"
          size="lg"
          className="w-full"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      {credentials ? (
        <section className="mt-6 grid gap-3 border-t border-border pt-5">
          <p className="text-sm font-medium">
            Try the demo. Its data is fictitious.
          </p>
          <dl className="grid gap-2 text-sm">
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Visitor email</dt>
              <dd className="break-all font-mono">{credentials.email}</dd>
            </div>
            <div className="grid gap-1">
              <dt className="text-muted-foreground">Visitor password</dt>
              <dd className="break-all font-mono">{credentials.password}</dd>
            </div>
          </dl>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setEmail(credentials.email)
              setPassword(credentials.password)
              signInButton.current?.focus()
            }}
          >
            Use demo login
          </Button>
        </section>
      ) : null}
    </AuthLayout>
  )
}
