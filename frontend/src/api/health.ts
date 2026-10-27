import type { components } from './schema'

export type Version = components['schemas']['AppVersion']

export const versionQueryKey = ['version']

export async function getVersion(): Promise<Version> {
  const response = await fetch('/api/version/')
  if (!response.ok) throw new Error('Version unavailable')
  const body: unknown = await response.json()
  if (
    typeof body !== 'object' ||
    body === null ||
    !('version' in body) ||
    typeof body.version !== 'string'
  ) {
    throw new Error('Unexpected version response')
  }
  return { version: body.version }
}

export async function getReadiness(): Promise<components['schemas']['Health']> {
  const response = await fetch('/api/health/ready/')
  if (!response.ok) throw new Error('Services unavailable')
  const body: unknown = await response.json()
  if (
    typeof body !== 'object' ||
    body === null ||
    !('status' in body) ||
    body.status !== 'ok'
  ) {
    throw new Error('Unexpected readiness response')
  }
  return { status: body.status }
}
