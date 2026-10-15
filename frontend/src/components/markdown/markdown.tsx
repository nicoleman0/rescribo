import { Component, lazy, Suspense, type ReactNode } from 'react'
import type { MarkdownProps } from './markdown-renderer'

const MarkdownRenderer = lazy(() => import('./markdown-renderer'))

export class MarkdownErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

function PlainText({ children }: { children: string }) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm">{children}</div>
  )
}

export function Markdown({ children, headingOffset = 0 }: MarkdownProps) {
  const fallback = <PlainText>{children}</PlainText>
  return (
    <MarkdownErrorBoundary
      fallback={
        <div className="grid gap-2">
          {fallback}
          <p className="text-xs text-muted-foreground">
            Formatted preview could not load.
          </p>
        </div>
      }
    >
      <Suspense fallback={fallback}>
        <MarkdownRenderer headingOffset={headingOffset}>
          {children}
        </MarkdownRenderer>
      </Suspense>
    </MarkdownErrorBoundary>
  )
}
