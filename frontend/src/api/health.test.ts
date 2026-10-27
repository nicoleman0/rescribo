import { expect, test, vi } from 'vitest'

import { getVersion } from './health'

test('rejects a non-OK response', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('no', { status: 503 })),
  )
  await expect(getVersion()).rejects.toThrow()
})

test('rejects a body without a string version', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('{"version": 12}', { status: 200 })),
  )
  await expect(getVersion()).rejects.toThrow()
})

test('returns the version', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response('{"version": "0.1.0"}', { status: 200 })),
  )
  await expect(getVersion()).resolves.toEqual({ version: '0.1.0' })
})
