import { Wordmark } from '@/components/brand/wordmark'
import type { ReactNode } from 'react'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-svh place-items-center bg-background p-5">
      <section className="w-full max-w-md rounded-card surface-raised p-6 shadow-elevation-2 sm:p-8">
        <Wordmark className="mb-6 h-7" />
        {children}
      </section>
    </main>
  )
}
