import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test } from 'vitest'
import type { ApiError } from '@/api/request'
import { problemKeys, type ProblemDetail } from '@/api/problems'
import { useProblemMutation } from './use-problem-mutation'

const old = { id: 'r1', version: 1, owner: null } as ProblemDetail
const ada = { id: 'm1', display_name: 'Ada' }
const key = problemKeys.detail('ws', 'r1')

function setup(run: () => Promise<ProblemDetail>) {
  const client = new QueryClient()
  client.setQueryData(key, old)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const hook = renderHook(
    () =>
      useProblemMutation<string>('ws', run, undefined, {
        problemId: 'r1',
        patch: (r) => ({ ...r, owner: ada }),
      }),
    { wrapper },
  )
  return { client, hook }
}

test('shows the new value before the request resolves', async () => {
  const { client, hook } = setup(() => new Promise(() => {}))
  act(() => hook.result.current.mutate('m1'))
  await waitFor(() =>
    expect(client.getQueryData<ProblemDetail>(key)?.owner).toEqual(ada),
  )
})

test('a network error restores the old value', async () => {
  const { client, hook } = setup(() => Promise.reject(new Error('down')))
  await act(() => hook.result.current.mutateAsync('m1').catch(() => {}))
  expect(client.getQueryData(key)).toEqual(old)
})

test('a 409 ends with the server record', async () => {
  const current = { ...old, version: 5 } as ProblemDetail
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
    () => useProblemMutation<string>('ws', () => new Promise(() => {})),
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
