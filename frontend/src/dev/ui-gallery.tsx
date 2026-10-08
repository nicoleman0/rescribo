import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  EmptyState,
  ErrorState,
  LoadingState,
  QueryState,
  ReadyState,
  RetryButton,
} from '@/components/states/async-states'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/components/status/status-badge'
import { STATUS_TONES } from '@/components/status/status-tone'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

export default function UiGalleryPage() {
  const [motionReplay, setMotionReplay] = useState(0)
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
            {STATUS_TONES.map((tone) => (
              <StatusBadge key={tone} tone={tone}>
                {tone}
              </StatusBadge>
            ))}
            <Badge variant="outline">Unassigned</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Avatar className="border-dashed">
                <AvatarFallback>?</AvatarFallback>
              </Avatar>
              Unassigned
            </span>
          </div>
        </CardContent>
      </Card>

      <section aria-labelledby="elevation-heading" className="grid gap-3">
        <h2 id="elevation-heading" className="text-sm font-semibold">
          Elevation
        </h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-card bg-card p-4 text-sm shadow-elevation-1">
            1: resting lists and cards
          </div>
          <div className="rounded-card surface-raised p-4 text-sm shadow-elevation-2">
            2: raised detail panels
          </div>
          <div className="rounded-card bg-card p-4 text-sm shadow-elevation-3">
            3: floating toasts and menus
          </div>
        </div>
      </section>

      <section aria-labelledby="motion-heading" className="grid gap-3">
        <h2 id="motion-heading" className="text-sm font-semibold">
          Motion
        </h2>
        <Button
          variant="outline"
          className="w-fit"
          onClick={() => setMotionReplay((value) => value + 1)}
        >
          Replay motion
        </Button>
        <div
          key={motionReplay}
          className="animate-page-enter grid gap-4 sm:grid-cols-2"
        >
          <ReadyState>
            <ul className="stagger-rows divide-y divide-border rounded-card bg-card shadow-elevation-1">
              {['First row', 'Second row', 'Third row'].map((label) => (
                <li key={label} className="p-3">
                  {label}
                </li>
              ))}
            </ul>
          </ReadyState>
          <div className="animate-panel-enter surface-raised rounded-card p-4 shadow-elevation-2">
            <ReadyState className="grid gap-3">
              <p>Raised panel</p>
              <StatusBadge tone={motionReplay % 2 ? 'success' : 'info'}>
                Status change
              </StatusBadge>
              <Button variant="secondary" className="w-fit">
                Secondary action
              </Button>
            </ReadyState>
          </div>
        </div>
      </section>

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
