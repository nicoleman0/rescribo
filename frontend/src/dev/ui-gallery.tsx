import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  QueryState,
  RetryButton,
} from '@/components/states/async-states'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

export default function UiGalleryPage() {
  const [isRetrying, setIsRetrying] = useState(false)
  const retry = () => {
    setIsRetrying(true)
    window.setTimeout(() => setIsRetrying(false), 400)
  }

  return (
    <div className="grid gap-8">
      <div>
        <p className="font-mono text-xs text-muted-foreground">
          Development only
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">
          UI gallery
        </h1>
        <p className="mt-2 max-w-xl text-muted-foreground">
          Shared primitives and query states in the Quiet direction. This route
          is not included in production builds.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Primitives</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6">
          <div className="flex flex-wrap items-center gap-2">
            <Button>Primary action</Button>
            <Button variant="secondary">Muted action</Button>
            <Button variant="outline">Outline action</Button>
            <Button variant="ghost">Quiet action</Button>
            <Button>
              Connect source
              <kbd className="rounded-control bg-primary-foreground/20 px-1 font-mono text-[10px]">
                C
              </kbd>
            </Button>
          </div>
          <Separator />
          <div className="flex flex-wrap gap-2">
            <Badge>New</Badge>
            <Badge className="bg-linked text-linked-foreground">Linked</Badge>
            <Badge className="bg-needs-review text-needs-review-foreground">
              Needs review
            </Badge>
            <Badge variant="outline">Unassigned</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 text-sm">
              <span className="size-2 rounded-pill bg-linked-foreground" />
              <Badge className="bg-linked text-linked-foreground">Linked</Badge>
            </span>
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Avatar className="border-dashed">
                <AvatarFallback>?</AvatarFallback>
              </Avatar>
              Unassigned
            </span>
          </div>
        </CardContent>
      </Card>

      <section aria-labelledby="loading-state-heading" className="grid gap-3">
        <h2 id="loading-state-heading" className="text-sm font-semibold">
          Loading state
        </h2>
        <Card>
          <CardContent className="p-4">
            <LoadingState label="Loading reports" />
          </CardContent>
        </Card>
      </section>

      <section aria-labelledby="empty-state-heading" className="grid gap-3">
        <h2 id="empty-state-heading" className="text-sm font-semibold">
          Empty state
        </h2>
        <EmptyState
          title="No reports yet"
          description="New customer reports will appear here when they arrive."
          action={<Button>Connect an intake source</Button>}
        />
      </section>

      <section aria-labelledby="error-state-heading" className="grid gap-3">
        <h2 id="error-state-heading" className="text-sm font-semibold">
          Error and retry states
        </h2>
        <ErrorState onRetry={retry} isRetrying={isRetrying} />
        <RetryButton onRetry={retry} isRetrying={isRetrying} />
      </section>

      <section aria-labelledby="query-state-heading" className="grid gap-3">
        <h2 id="query-state-heading" className="text-sm font-semibold">
          TanStack Query pattern
        </h2>
        <div className="grid gap-4 lg:grid-cols-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Loading</CardTitle>
            </CardHeader>
            <CardContent>
              <QueryState status="loading">Ready content</QueryState>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Empty</CardTitle>
            </CardHeader>
            <CardContent>
              <QueryState status="empty">Ready content</QueryState>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Error</CardTitle>
            </CardHeader>
            <CardContent>
              <QueryState
                status="error"
                onRetry={retry}
                isRetrying={isRetrying}
              >
                Ready content
              </QueryState>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Ready</CardTitle>
            </CardHeader>
            <CardContent>
              <QueryState status="ready">
                <p className="text-sm text-muted-foreground">Reports loaded.</p>
              </QueryState>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  )
}
