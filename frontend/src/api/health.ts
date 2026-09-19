import type { components } from './schema'

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
