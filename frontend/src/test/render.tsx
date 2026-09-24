import { vi } from 'vitest'
import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import type { Session } from '@/api/auth'
import { WorkspaceProvider } from '@/components/auth/workspace-provider'
import { LocationProbe } from './location-probe'

export const testMembership: Session['memberships'][number] = {
  membership_id: 'm-1',
  role: 'member',
  workspace: { id: 'ws-1', name: 'Example', slug: 'example' },
}

export type TestRoute = { path: string; element: ReactElement }

/** Render workspace routes with a fresh query client and no retries. */
export function renderWorkspaceRoutes(
  routes: TestRoute[],
  initialPath: string,
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <WorkspaceProvider membership={testMembership}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            {routes.map((route) => (
              <Route
                key={route.path}
                path={route.path}
                element={route.element}
              />
            ))}
          </Routes>
          <LocationProbe />
        </MemoryRouter>
      </WorkspaceProvider>
    </QueryClientProvider>,
  )
}

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

/** Stub fetch with handlers matched by pathname; unmatched calls fail loudly. */
export function stubApi(handlers: Record<string, Handler>) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      const key = `${init?.method ?? 'GET'} ${url.pathname}`
      const handler = handlers[key]
      if (!handler) throw new Error(`Unexpected request: ${key}`)
      return handler(url, init)
    },
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
