import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import { reportKeys } from '@/api/reports'
import { useNavigationCounts } from './use-navigation-counts'

test('reads the two filtered list counts and refetches on report invalidation', async () => {
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    return new Response(
      JSON.stringify({ count: url.includes('reports') ? 3 : 2, results: [] }),
      { status: 200 },
    )
  })
  vi.stubGlobal('fetch', fetcher)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useNavigationCounts('ws-1'), { wrapper })
  await waitFor(() =>
    expect(result.current).toEqual({ reports: 3, followUps: 2 }),
  )
  const before = fetcher.mock.calls.length
  await client.invalidateQueries({ queryKey: reportKeys.all('ws-1') })
  await waitFor(() => expect(fetcher.mock.calls.length).toBeGreaterThan(before))
})

test('makes no request without a workspace', async () => {
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  const client = new QueryClient()
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useNavigationCounts(), { wrapper })
  expect(result.current).toEqual({ reports: undefined, followUps: undefined })
  expect(fetcher).not.toHaveBeenCalled()
})
