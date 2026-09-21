import type { ReactNode } from 'react'
import { Inbox, RefreshCw, TriangleAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

export type QueryStateStatus = 'loading' | 'empty' | 'error' | 'ready'

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div
      role="status"
      aria-label={label}
      aria-busy="true"
      className="grid gap-3"
    >
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-11 w-11/12" />
      <Skeleton className="h-11 w-4/5" />
    </div>
  )
}

export function RetryButton({
  onRetry,
  isRetrying = false,
}: {
  onRetry: () => void
  isRetrying?: boolean
}) {
  return (
    <Button variant="outline" onClick={onRetry} disabled={isRetrying}>
      <RefreshCw
        aria-hidden="true"
        className={isRetrying ? 'animate-spin' : undefined}
      />
      {isRetrying ? 'Retrying…' : 'Try again'}
    </Button>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <Card className="border-dashed bg-transparent shadow-none">
      <CardContent className="grid min-h-56 place-items-center gap-3 p-8 text-center">
        <span className="grid size-10 place-items-center rounded-pill bg-selected text-muted-foreground">
          <Inbox aria-hidden="true" className="size-5" />
        </span>
        <div className="max-w-sm">
          <h1 className="text-base font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  )
}

export function ErrorState({
  title = 'Could not load this view',
  description = 'Check the connection and try again.',
  onRetry,
  isRetrying = false,
}: {
  title?: string
  description?: string
  onRetry?: () => void
  isRetrying?: boolean
}) {
  return (
    <Alert variant="destructive" className="grid gap-3">
      <TriangleAlert aria-hidden="true" />
      <div>
        <AlertTitle>{title}</AlertTitle>
        <AlertDescription>{description}</AlertDescription>
      </div>
      {onRetry ? (
        <RetryButton onRetry={onRetry} isRetrying={isRetrying} />
      ) : null}
    </Alert>
  )
}

export function QueryState({
  status,
  onRetry,
  isRetrying,
  children,
}: {
  status: QueryStateStatus
  onRetry?: () => void
  isRetrying?: boolean
  children: ReactNode
}) {
  if (status === 'loading') return <LoadingState />
  if (status === 'empty') {
    return (
      <EmptyState
        title="Nothing here yet"
        description="New work will appear here when it is ready."
      />
    )
  }
  if (status === 'error') {
    return <ErrorState onRetry={onRetry} isRetrying={isRetrying} />
  }
  return <>{children}</>
}
