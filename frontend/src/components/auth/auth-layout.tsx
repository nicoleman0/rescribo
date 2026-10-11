import { Wordmark } from '@/components/brand/wordmark'
import { PageTitle } from '@/components/layout/page-title'
import type { ReactNode } from 'react'

const PRODUCT_LINE = 'Customer feedback. Engineering work. Follow-up.'

export function AuthLayout({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <main className="grid min-h-svh place-items-center bg-background p-5">
      <PageTitle title={title} />
      <div className="grid w-full max-w-5xl items-center gap-8 lg:grid-cols-2 lg:gap-16">
        <header className="grid gap-4 lg:justify-self-end">
          <Wordmark className="h-8" />
          <p className="max-w-md text-lg text-muted-foreground">
            {PRODUCT_LINE}
          </p>
        </header>
        <section className="w-full rounded-card surface-raised p-6 shadow-elevation-2 sm:p-8">
          <h1 className="mb-5 text-xl font-semibold">{title}</h1>
          {children}
        </section>
      </div>
    </main>
  )
}
