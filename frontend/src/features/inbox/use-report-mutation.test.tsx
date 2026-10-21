import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test } from 'vitest'
import type { ApiError } from '@/api/request'
import { reportKeys, type ReportDetail } from '@/api/reports'
import { useReportMutation } from './use-report-mutation'

const old = { id: 'r1', version: 1, assignee: null } as ReportDetail
const ada = { id: 'm1', display_name: 'Ada' }
const key = reportKeys.detail('ws', 'r1')

function setup(run: () => Promise<ReportDetail>) {
  const client = new QueryClient()
  client.setQueryData(key, old)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const hook = renderHook(
    () =>
      useReportMutation<string>('ws', run, undefined, {
        reportId: 'r1',
        patch: (r) => ({ ...r, assignee: ada }),
      }),
    { wrapper },
  )
  return { client, hook }
}

test('shows the new value before the request resolves', async () => {
  const { client, hook } = setup(() => new Promise(() => {}))
  act(() => hook.result.current.mutate('m1'))
  await waitFor(() =>
    expect(client.getQueryData<ReportDetail>(key)?.assignee).toEqual(ada),
  )
})

test('a network error restores the old value', async () => {
  const { client, hook } = setup(() => Promise.reject(new Error('down')))
  await act(() => hook.result.current.mutateAsync('m1').catch(() => {}))
  expect(client.getQueryData(key)).toEqual(old)
})

test('a 409 ends with the server record', async () => {
  const current = { ...old, version: 5 } as ReportDetail
  const error = Object.assign(new Error('Changed'), {
    status: 409,
    current,
  }) as ApiError
  const { client, hook } = setup(() => Promise.reject(error))
  await act(() => hook.result.current.mutateAsync('m1').catch(() => {}))
  expect(client.getQueryData(key)).toEqual(current)
})

test('without the option the cache is untouched until the reply', async () => {
  const client = new QueryClient()
  client.setQueryData(key, old)
  const { result } = renderHook(
    () => useReportMutation<string>('ws', () => new Promise(() => {})),
    {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    },
  )
  act(() => result.current.mutate('m1'))
  await waitFor(() => expect(result.current.isPending).toBe(true))
  expect(client.getQueryData(key)).toEqual(old)
})
