import type { ReactNode } from 'react'

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="grid min-h-svh place-items-center bg-background p-5">
      <section className="w-full max-w-md rounded-card border border-border bg-card p-6 shadow-sm sm:p-8">
        <p className="mb-6 text-sm font-semibold">Rescribo</p>
        {children}
      </section>
    </main>
  )
}
