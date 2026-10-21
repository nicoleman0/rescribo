import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test } from 'vitest'
import type { ApiError } from '@/api/request'
import { followUpKeys, type FollowUpDetail } from '@/api/follow-ups'
import { useFollowUpMutation } from './follow-ups-mutation'

const old = { id: 'r1', recipient: null } as unknown as FollowUpDetail
const ada = { member: { id: 'm1', display_name: 'Ada' }, has_slack_link: true }
const key = followUpKeys.detail('ws', 'r1')

function setup(run: () => Promise<FollowUpDetail>) {
  const client = new QueryClient()
  client.setQueryData(key, old)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const hook = renderHook(
    () =>
      useFollowUpMutation<string>('ws', run, undefined, {
        followUpId: 'r1',
        patch: (r) => ({ ...r, recipient: ada }),
      }),
    { wrapper },
  )
  return { client, hook }
}

test('shows the new value before the request resolves', async () => {
  const { client, hook } = setup(() => new Promise(() => {}))
  act(() => hook.result.current.mutate('m1'))
  await waitFor(() =>
    expect(client.getQueryData<FollowUpDetail>(key)?.recipient).toEqual(ada),
  )
})

test('a network error restores the old value', async () => {
  const { client, hook } = setup(() => Promise.reject(new Error('down')))
  await act(() => hook.result.current.mutateAsync('m1').catch(() => {}))
  expect(client.getQueryData(key)).toEqual(old)
})

test('a 409 ends with the server record', async () => {
  const current = {
    ...old,
    id: 'r1',
    recipient: ada,
  } as unknown as FollowUpDetail
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
    () => useFollowUpMutation<string>('ws', () => new Promise(() => {})),
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
