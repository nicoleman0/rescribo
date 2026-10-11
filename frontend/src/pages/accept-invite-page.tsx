import { useState, type FormEvent } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiRequest, type ApiError } from '@/api/request'
import { csrf, getSession, sessionQueryKey, type Session } from '@/api/auth'
import { useQueryClient } from '@tanstack/react-query'
import { AuthLayout } from '@/components/auth/auth-layout'
import { Field } from '@/components/forms/field'
import { fieldError } from '@/components/forms/field-error'
import { FormErrorMessage } from '@/components/forms/form-error-message'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ErrorState, LoadingState } from '@/components/states/async-states'

type Preview = { status: string; workspace_name?: string }

export function AcceptInvitePage() {
  const { token = '' } = useParams()
  const preview = useQuery({
    queryKey: ['invite-preview', token],
    queryFn: async () => {
      await csrf()
      return apiRequest<Preview>('invitations/preview/', { token })
    },
    retry: false,
    enabled: Boolean(token),
  })
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const currentSession = useQuery({
    queryKey: sessionQueryKey,
    queryFn: getSession,
    retry: false,
    enabled: preview.data?.status === 'requires_sign_in',
  })
  const accept = useMutation({
    mutationFn: async () => {
      await csrf()
      return apiRequest<Session>('invitations/accept/', {
        token,
        full_name: name,
        password,
      })
    },
    onSuccess: (session) => {
      queryClient.setQueryData(sessionQueryKey, session)
      navigate('/inbox', { replace: true })
    },
  })
  const acceptError = accept.error as ApiError | null
  function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirmation) {
      setPasswordError('Passwords do not match.')
      return
    }
    setPasswordError('')
    accept.mutate()
  }
  return (
    <AuthLayout title="Accept invitation">
      {preview.isPending ? (
        <LoadingState label="Checking invitation" />
      ) : preview.isError ? (
        <ErrorState
          title="Could not check this invitation"
          description="Retry the check. If the invitation has expired, ask an owner for a new link."
          onRetry={() => void preview.refetch()}
          isRetrying={preview.isFetching}
        />
      ) : preview.data?.status === 'unknown' ||
        preview.data?.status === 'expired' ? (
        <div className="grid gap-2">
          <p role="status">
            This invitation has expired or is no longer available.
          </p>
          <p className="text-sm text-muted-foreground">
            Ask a workspace owner for a new invitation.
          </p>
          <Link className="w-fit underline" to="/sign-in">
            Sign in
          </Link>
        </div>
      ) : preview.data?.status === 'requires_sign_in' &&
        currentSession.isPending ? (
        <LoadingState label="Checking your session" />
      ) : preview.data?.status === 'requires_sign_in' &&
        currentSession.isError &&
        (currentSession.error as ApiError).status !== 401 ? (
        <ErrorState
          title="Could not check your session"
          description="Retry the session check, or sign in and open this invitation again."
          onRetry={() => void currentSession.refetch()}
          isRetrying={currentSession.isFetching}
        />
      ) : preview.data?.status === 'requires_sign_in' &&
        !currentSession.data ? (
        <>
          <p className="my-3 text-sm">
            Join {preview.data.workspace_name}. This email already has an
            account. Enter its password to accept.
          </p>
          <form
            className="grid gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              accept.mutate()
            }}
          >
            <Field
              id="current-password"
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={fieldError(acceptError, 'password')}
            />
            {acceptError && !acceptError.fieldErrors?.password ? (
              <Alert variant="destructive">
                <AlertDescription>
                  <FormErrorMessage error={acceptError} />
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={accept.isPending}
            >
              Accept invitation
            </Button>
          </form>
        </>
      ) : preview.data?.status === 'requires_sign_in' ? (
        <div className="grid gap-4">
          <p>Confirm acceptance while signed in to the invited account.</p>
          <Button
            type="button"
            size="lg"
            className="w-full"
            disabled={accept.isPending}
            onClick={() => accept.mutate()}
          >
            Accept invitation
          </Button>
          {acceptError ? (
            <Alert variant="destructive">
              <AlertDescription>
                <FormErrorMessage error={acceptError} />
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
      ) : (
        <>
          <p className="my-3 text-sm">Join {preview.data?.workspace_name}.</p>
          <form className="grid gap-4" onSubmit={submit}>
            <Field
              id="full-name"
              label="Full name"
              autoComplete="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Field
              id="new-password"
              label="Password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              error={passwordError || fieldError(acceptError, 'password')}
            />
            <Field
              id="confirm-password"
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              required
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
            />
            {acceptError ? (
              <Alert variant="destructive">
                <AlertDescription>
                  <FormErrorMessage error={acceptError} />
                </AlertDescription>
              </Alert>
            ) : null}
            <Button
              type="submit"
              size="lg"
              className="w-full"
              disabled={accept.isPending}
            >
              Accept invitation
            </Button>
          </form>
        </>
      )}
    </AuthLayout>
  )
}
