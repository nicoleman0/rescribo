import { useQuery } from '@tanstack/react-query'
import { Activity, RefreshCw } from 'lucide-react'
import { getReadiness } from '@/api/health'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function DevelopmentStatusPage() {
  const health = useQuery({
    queryKey: ['readiness'],
    queryFn: getReadiness,
    retry: false,
  })

  return (
    <main className="mx-auto grid min-h-svh w-full max-w-2xl content-center gap-6 px-6 py-12">
      <div>
        <p className="font-mono text-xs text-muted-foreground">
          Development workspace
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.04em]">
          Feedback inbox
        </h1>
        <p className="mt-2 max-w-lg text-muted-foreground">
          Customer reports, engineering work, and the people waiting for an
          answer.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity aria-hidden="true" className="size-4 text-primary" />
            Environment
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4">
          {health.isPending ? (
            <p role="status" aria-busy="true" className="text-muted-foreground">
              Checking services…
            </p>
          ) : health.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Services unavailable</AlertTitle>
              <AlertDescription>
                Start the API, PostgreSQL, and Redis, then check again.
              </AlertDescription>
            </Alert>
          ) : (
            <p role="status">API, PostgreSQL, and Redis are ready.</p>
          )}
          <Button
            className="w-fit"
            onClick={() => void health.refetch()}
            disabled={health.isFetching}
          >
            <RefreshCw aria-hidden="true" />
            {health.isFetching ? 'Checking…' : 'Check again'}
          </Button>
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">
        Product workflows are not built yet. This page checks the development
        services.
      </p>
    </main>
  )
}
